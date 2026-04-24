from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alarm


class AlarmRepository:
    async def get_active_for_user(self, session: AsyncSession, user_id: int) -> Alarm | None:
        result = await session.execute(
            select(Alarm).where(Alarm.user_id == user_id, Alarm.is_active.is_(True)).order_by(desc(Alarm.created_at)).limit(1)
        )
        return result.scalar_one_or_none()
