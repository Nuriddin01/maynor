from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserPreference


class PreferenceRepository:
    async def get_by_user_id(self, session: AsyncSession, user_id: int) -> UserPreference | None:
        result = await session.execute(select(UserPreference).where(UserPreference.user_id == user_id))
        return result.scalar_one_or_none()
