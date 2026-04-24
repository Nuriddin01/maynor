from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionRequest, SleepEntry, User
from app.schemas import HistoricalSignal, SessionRequestCreate, SleepEntryCreate
from app.utils.time_utils import utc_now


class SleepService:
    async def create_session_request(
        self,
        session: AsyncSession,
        user: User,
        payload: SessionRequestCreate,
    ) -> SessionRequest:
        request = SessionRequest(
            user_id=user.id,
            requested_mode=payload.requested_mode,
            free_time_minutes=payload.free_time_minutes,
            slept_last_night_minutes=payload.slept_last_night_minutes,
            current_energy_1_5=payload.current_energy_1_5,
            current_sleepiness_1_5=payload.current_sleepiness_1_5,
            current_stress_1_5=payload.current_stress_1_5,
            wants_alarm=payload.wants_alarm,
            recommendation_snapshot_json=payload.recommendation_snapshot_json,
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request

    async def create_sleep_entry(
        self,
        session: AsyncSession,
        user: User,
        payload: SleepEntryCreate,
    ) -> SleepEntry:
        entry = SleepEntry(
            user_id=user.id,
            entry_date=utc_now().date(),
            mode=payload.mode,
            duration_minutes=payload.duration_minutes,
            subjective_sleep_quality_1_5=payload.subjective_sleep_quality_1_5,
            felt_after_waking_1_5=payload.felt_after_waking_1_5,
            stress_before_sleep_1_5=payload.stress_before_sleep_1_5,
            sleepiness_before_sleep_1_5=payload.sleepiness_before_sleep_1_5,
            helpfulness_1_5=payload.helpfulness_1_5,
            notes=payload.notes,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    async def create_sleep_entry_from_latest_session(
        self,
        session: AsyncSession,
        user: User,
        payload: SleepEntryCreate,
    ) -> SleepEntry:
        latest_session = await self.get_latest_session_request(session, user.id)
        mode = latest_session.requested_mode if latest_session else "manual_checkin"
        session_payload = payload.model_copy(update={"mode": mode})
        if latest_session:
            session_payload = session_payload.model_copy(
                update={
                    "stress_before_sleep_1_5": latest_session.current_stress_1_5,
                    "sleepiness_before_sleep_1_5": latest_session.current_sleepiness_1_5,
                }
            )
        return await self.create_sleep_entry(session, user, session_payload)

    async def get_latest_session_request(self, session: AsyncSession, user_id: int) -> SessionRequest | None:
        result = await session.execute(
            select(SessionRequest)
            .where(
                SessionRequest.user_id == user_id,
                SessionRequest.created_at >= utc_now() - timedelta(hours=24),
            )
            .order_by(desc(SessionRequest.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_recent_history(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 10,
    ) -> list[SleepEntry]:
        result = await session.execute(
            select(SleepEntry)
            .where(SleepEntry.user_id == user_id)
            .order_by(desc(SleepEntry.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_history_for_recommendation(
        self,
        session: AsyncSession,
        user_id: int,
        days: int = 7,
    ) -> list[HistoricalSignal]:
        result = await session.execute(
            select(SleepEntry)
            .where(
                SleepEntry.user_id == user_id,
                SleepEntry.created_at >= utc_now() - timedelta(days=days),
            )
            .order_by(desc(SleepEntry.created_at))
        )
        return [
            HistoricalSignal(
                mode=entry.mode,
                duration_minutes=entry.duration_minutes,
                subjective_sleep_quality_1_5=entry.subjective_sleep_quality_1_5,
                felt_after_waking_1_5=entry.felt_after_waking_1_5,
                helpfulness_1_5=entry.helpfulness_1_5,
                created_at=entry.created_at,
            )
            for entry in result.scalars().all()
        ]
