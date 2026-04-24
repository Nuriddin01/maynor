from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Alarm, User
from app.schemas import AlarmCreateResult, AlarmStopResult
from app.utils.time_utils import local_clock_to_utc, minutes_from_now_to_utc


class AlarmSchedulerProtocol(Protocol):
    def schedule_alarm(self, alarm_id: int, run_at: datetime) -> None: ...

    def remove_alarm(self, alarm_id: int) -> None: ...


@dataclass
class ActiveAlarmInfo:
    id: int
    alarm_time: datetime
    code: str
    repeat_attempts: int


class AlarmService:
    def __init__(self, settings: Settings, scheduler: AlarmSchedulerProtocol) -> None:
        self.settings = settings
        self.scheduler = scheduler

    async def get_active_alarm_for_user(self, session: AsyncSession, user_id: int) -> Alarm | None:
        result = await session.execute(
            select(Alarm)
            .where(Alarm.user_id == user_id, Alarm.is_active.is_(True))
            .order_by(Alarm.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_alarm_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> Alarm | None:
        result = await session.execute(
            select(Alarm)
            .join(Alarm.user)
            .options(selectinload(Alarm.user))
            .where(User.telegram_id == telegram_id, Alarm.is_active.is_(True))
            .order_by(Alarm.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_alarm_in_minutes(
        self,
        session: AsyncSession,
        user: User,
        minutes: int,
    ) -> AlarmCreateResult:
        existing = await self.get_active_alarm_for_user(session, user.id)
        if existing:
            raise ValueError("У пользователя уже есть активный будильник.")

        alarm = Alarm(
            user_id=user.id,
            alarm_time=minutes_from_now_to_utc(minutes),
            code=self.generate_code(self.settings.alarm_code_length),
            repeat_attempts=0,
            max_repeat_attempts=self.settings.max_alarm_repeat_attempts,
            is_active=True,
        )
        session.add(alarm)
        await session.commit()
        await session.refresh(alarm)
        self.scheduler.schedule_alarm(alarm.id, alarm.alarm_time)
        return AlarmCreateResult(alarm_id=alarm.id, alarm_time=alarm.alarm_time, code=alarm.code)

    async def create_alarm_at_clock(
        self,
        session: AsyncSession,
        user: User,
        clock_value: str,
    ) -> AlarmCreateResult:
        existing = await self.get_active_alarm_for_user(session, user.id)
        if existing:
            raise ValueError("У пользователя уже есть активный будильник.")

        alarm = Alarm(
            user_id=user.id,
            alarm_time=local_clock_to_utc(clock_value, user.timezone),
            code=self.generate_code(self.settings.alarm_code_length),
            repeat_attempts=0,
            max_repeat_attempts=self.settings.max_alarm_repeat_attempts,
            is_active=True,
        )
        session.add(alarm)
        await session.commit()
        await session.refresh(alarm)
        self.scheduler.schedule_alarm(alarm.id, alarm.alarm_time)
        return AlarmCreateResult(alarm_id=alarm.id, alarm_time=alarm.alarm_time, code=alarm.code)

    async def confirm_alarm_stop(
        self,
        session: AsyncSession,
        telegram_id: int,
        code: str,
    ) -> AlarmStopResult:
        alarm = await self.get_active_alarm_by_telegram_id(session, telegram_id)
        if alarm is None:
            return AlarmStopResult(stopped=False, reason="no_active_alarm")

        if alarm.code != code:
            return AlarmStopResult(stopped=False, reason="wrong_code", alarm_id=alarm.id)

        alarm.is_active = False
        alarm.stop_confirmed_at = datetime.now(timezone.utc)
        await session.commit()
        self.scheduler.remove_alarm(alarm.id)
        return AlarmStopResult(stopped=True, reason="stopped", alarm_id=alarm.id)

    @staticmethod
    def generate_code(length: int = 4) -> str:
        digits = string.digits
        return "".join(secrets.choice(digits) for _ in range(length))
