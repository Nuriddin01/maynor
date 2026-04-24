from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionRequest


class SessionRequestRepository:
    async def latest_for_user(self, session: AsyncSession, user_id: int) -> SessionRequest | None:
        result = await session.execute(
            select(SessionRequest).where(SessionRequest.user_id == user_id).order_by(desc(SessionRequest.created_at)).limit(1)
        )
        return result.scalar_one_or_none()
