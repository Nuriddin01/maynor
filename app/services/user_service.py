from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.constants import AUDIO_TYPES
from app.models import User, UserPreference


class UserService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def get_or_create_user(self, session: AsyncSession, telegram_id: int, name: str | None) -> User:
        result = await session.execute(
            select(User).options(selectinload(User.preferences)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            if name and user.name != name:
                user.name = name
                await session.commit()
            await self.ensure_preferences(session, user)
            return user

        user = User(
            telegram_id=telegram_id,
            name=name,
            timezone=self.settings.app_timezone,
            preferred_language=self.settings.default_language,
        )
        session.add(user)
        await session.flush()
        session.add(
            UserPreference(
                user_id=user.id,
                preferred_audio="silence",
                time_format=self.settings.default_time_format,
            )
        )
        await session.commit()
        await session.refresh(user)
        return user

    async def ensure_preferences(self, session: AsyncSession, user: User) -> UserPreference:
        if user.preferences is not None:
            return user.preferences
        preference = UserPreference(
            user_id=user.id,
            preferred_audio="silence",
            time_format=self.settings.default_time_format,
        )
        session.add(preference)
        await session.commit()
        await session.refresh(preference)
        user.preferences = preference
        return preference

    async def update_timezone(self, session: AsyncSession, user: User, timezone_name: str) -> None:
        user.timezone = timezone_name
        await session.commit()

    async def update_language(self, session: AsyncSession, user: User, language: str) -> None:
        user.preferred_language = language
        await session.commit()

    async def update_audio_preferences(
        self,
        session: AsyncSession,
        user: User,
        preferred_audio: str | None = None,
        dislikes_white_noise: bool | None = None,
        likes_rain: bool | None = None,
        likes_forest: bool | None = None,
        likes_silence: bool | None = None,
        default_nap_minutes: int | None = None,
        reminders_enabled: bool | None = None,
    ) -> None:
        preference = await self.ensure_preferences(session, user)
        if preferred_audio is not None and preferred_audio in AUDIO_TYPES:
            preference.preferred_audio = preferred_audio
        if dislikes_white_noise is not None:
            preference.dislikes_white_noise = dislikes_white_noise
        if likes_rain is not None:
            preference.likes_rain = likes_rain
        if likes_forest is not None:
            preference.likes_forest = likes_forest
        if likes_silence is not None:
            preference.likes_silence = likes_silence
        if default_nap_minutes is not None:
            preference.default_nap_minutes = default_nap_minutes
        if reminders_enabled is not None:
            preference.reminders_enabled = reminders_enabled
        await session.commit()

    async def update_toggle_preferences(self, session: AsyncSession, user: User, *, time_format: str | None = None) -> None:
        preference = await self.ensure_preferences(session, user)
        if time_format is not None:
            preference.time_format = time_format
        await session.commit()

    async def settings_overview(self, session: AsyncSession, user: User) -> dict:
        preference = await self.ensure_preferences(session, user)
        return {
            "timezone": user.timezone,
            "language": user.preferred_language,
            "preferred_audio": preference.preferred_audio or "не выбрано",
            "time_format": preference.time_format,
            "dislikes_white_noise": preference.dislikes_white_noise,
            "default_nap_minutes": preference.default_nap_minutes,
            "reminders_enabled": preference.reminders_enabled,
            "premium_status": user.premium_status,
        }
