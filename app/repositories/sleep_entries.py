from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SleepEntry


class SleepEntryRepository:
    async def list_recent(self, session: AsyncSession, user_id: int, limit: int = 10) -> list[SleepEntry]:
        result = await session.execute(
            select(SleepEntry).where(SleepEntry.user_id == user_id).order_by(desc(SleepEntry.created_at)).limit(limit)
        )
        return list(result.scalars().all())
