from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.user_service import UserService


class DbSessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        user_service: UserService,
    ) -> None:
        self.session_factory = session_factory
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session

            from_user = getattr(event, "from_user", None)
            if from_user is not None:
                data["db_user"] = await self.user_service.get_or_create_user(
                    session=session,
                    telegram_id=from_user.id,
                    name=from_user.full_name,
                )

            return await handler(event, data)
