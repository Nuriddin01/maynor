from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.user_service import UserService


class PreferenceService:
    def __init__(self, user_service: UserService) -> None:
        self.user_service = user_service

    async def set_default_nap_minutes(self, session: AsyncSession, user: User, minutes: int) -> None:
        await self.user_service.update_audio_preferences(session, user, default_nap_minutes=minutes)

    async def toggle_reminders(self, session: AsyncSession, user: User, enabled: bool) -> None:
        await self.user_service.update_audio_preferences(session, user, reminders_enabled=enabled)
