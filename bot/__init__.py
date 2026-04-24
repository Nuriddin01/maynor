from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.user_service import UserService
from bot.handlers.alarms import router as alarms_router
from bot.handlers.day import router as day_router
from bot.handlers.help import router as help_router
from bot.handlers.history import router as history_router
from bot.handlers.night import router as night_router
from bot.handlers.power_nap import router as power_nap_router
from bot.handlers.premium import router as premium_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.stats import router as stats_router
from bot.handlers.wake_checkin import router as wake_router
from bot.middlewares.db import DbSessionMiddleware


def build_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    user_service: UserService,
) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(DbSessionMiddleware(session_factory, user_service))

    dispatcher.include_router(start_router)
    dispatcher.include_router(help_router)
    dispatcher.include_router(night_router)
    dispatcher.include_router(day_router)
    dispatcher.include_router(power_nap_router)
    dispatcher.include_router(wake_router)
    dispatcher.include_router(history_router)
    dispatcher.include_router(stats_router)
    dispatcher.include_router(alarms_router)
    dispatcher.include_router(settings_router)
    dispatcher.include_router(premium_router)

    return dispatcher
