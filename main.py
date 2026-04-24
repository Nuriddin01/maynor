from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from dotenv import load_dotenv

from app.config import get_settings
from app.db import create_engine, create_session_factory, init_db
from app.recommendation_engine import RecommendationEngine
from app.scheduler import BotScheduler
from app.services.alarm_service import AlarmService
from app.services.recommendation_service import RecommendationService
from app.services.sleep_service import SleepService
from app.services.stats_service import StatsService
from app.services.user_service import UserService
from bot import build_dispatcher


async def main() -> None:
    load_dotenv()
    settings = get_settings()

    if settings.telegram_bot_token == "TEST_TOKEN":
        raise RuntimeError("Set SSB_TELEGRAM_BOT_TOKEN in .env before starting the bot.")

    settings.data_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    await init_db(engine)

    bot = Bot(token=settings.telegram_bot_token)
    scheduler = BotScheduler(settings)
    scheduler.attach(bot, session_factory)
    scheduler.start()
    await scheduler.restore_active_alarms()

    user_service = UserService(settings)
    sleep_service = SleepService()
    recommendation_engine = RecommendationEngine()
    recommendation_service = RecommendationService(recommendation_engine, sleep_service, user_service)
    stats_service = StatsService()
    alarm_service = AlarmService(settings, scheduler)

    dispatcher = build_dispatcher(session_factory, user_service)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            alarm_service=alarm_service,
            recommendation_service=recommendation_service,
            sleep_service=sleep_service,
            stats_service=stats_service,
            user_service=user_service,
        )
    finally:
        await scheduler.shutdown()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
