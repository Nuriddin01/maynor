from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.constants import DISCLAIMER_TEXT
from app.models import Alarm, User
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.bot: Bot | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    def attach(self, bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.bot = bot
        self.session_factory = session_factory

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def schedule_alarm(self, alarm_id: int, run_at) -> None:
        self.scheduler.add_job(
            self.run_alarm,
            trigger="date",
            run_date=run_at,
            id=self._job_id(alarm_id),
            replace_existing=True,
            kwargs={"alarm_id": alarm_id},
        )

    def remove_alarm(self, alarm_id: int) -> None:
        try:
            self.scheduler.remove_job(self._job_id(alarm_id))
        except JobLookupError:
            return

    async def restore_active_alarms(self) -> None:
        if self.session_factory is None:
            raise RuntimeError("Session factory is not attached to scheduler.")

        async with self.session_factory() as session:
            result = await session.execute(select(Alarm).where(Alarm.is_active.is_(True)))
            alarms = result.scalars().all()
            now = utc_now()
            for alarm in alarms:
                run_at = alarm.alarm_time if alarm.alarm_time > now else now + timedelta(seconds=1)
                self.schedule_alarm(alarm.id, run_at)
                logger.info("Restored alarm %s for %s", alarm.id, run_at.isoformat())

    async def run_alarm(self, alarm_id: int) -> None:
        if self.bot is None or self.session_factory is None:
            logger.warning("Scheduler is missing bot or session factory.")
            return

        async with self.session_factory() as session:
            result = await session.execute(
                select(Alarm)
                .options(selectinload(Alarm.user).selectinload(User.preferences))
                .where(Alarm.id == alarm_id)
            )
            alarm = result.scalar_one_or_none()
            if alarm is None or not alarm.is_active:
                self.remove_alarm(alarm_id)
                return

            attempt = alarm.repeat_attempts + 1
            remaining = alarm.max_repeat_attempts - attempt
            suffix = (
                "Это последнее напоминание."
                if remaining <= 0
                else f"Если не ответите кодом, я напомню еще {remaining} раз(а)."
            )

            await self.bot.send_message(
                chat_id=alarm.user.telegram_id,
                text=(
                    "Будильник сработал.\n\n"
                    f"Код остановки: `{alarm.code}`\n"
                    "Введите его в чат, чтобы выключить напоминания.\n\n"
                    f"{suffix}\n\n{DISCLAIMER_TEXT}"
                ),
                parse_mode="Markdown",
            )

            alarm.repeat_attempts = attempt
            if attempt >= alarm.max_repeat_attempts:
                alarm.is_active = False
                self.remove_alarm(alarm_id)
            else:
                next_run = utc_now() + timedelta(seconds=self.settings.alarm_repeat_interval_seconds)
                self.schedule_alarm(alarm.id, next_run)

            await session.commit()

    @staticmethod
    def _job_id(alarm_id: int) -> str:
        return f"alarm:{alarm_id}"
