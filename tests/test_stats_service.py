from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import create_engine, create_session_factory, init_db
from app.schemas import SleepEntryCreate
from app.services.sleep_service import SleepService
from app.services.stats_service import StatsService
from app.services.user_service import UserService


def make_local_db_path(filename_prefix: str) -> Path:
    runtime_dir = Path(".test_runtime")
    runtime_dir.mkdir(exist_ok=True)
    return runtime_dir / f"{filename_prefix}_{uuid4().hex}.db"


@pytest.mark.asyncio
async def test_stats_summary_contains_mode_patterns() -> None:
    db_path = make_local_db_path("stats_test")
    settings = Settings(
        telegram_bot_token="token",
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )
    engine = create_engine(settings)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    user_service = UserService(settings)
    sleep_service = SleepService()
    stats_service = StatsService()

    async with session_factory() as session:  # type: AsyncSession
        user = await user_service.get_or_create_user(session, telegram_id=3003, name="Stats User")
        await sleep_service.create_sleep_entry(
            session,
            user,
            SleepEntryCreate(
                mode="power_nap_15",
                duration_minutes=15,
                subjective_sleep_quality_1_5=4,
                felt_after_waking_1_5=4,
                helpfulness_1_5=5,
            ),
        )
        await sleep_service.create_sleep_entry(
            session,
            user,
            SleepEntryCreate(
                mode="power_nap_15",
                duration_minutes=15,
                subjective_sleep_quality_1_5=4,
                felt_after_waking_1_5=5,
                helpfulness_1_5=4,
            ),
        )
        await sleep_service.create_sleep_entry(
            session,
            user,
            SleepEntryCreate(
                mode="recovery_break",
                duration_minutes=8,
                subjective_sleep_quality_1_5=3,
                felt_after_waking_1_5=3,
                helpfulness_1_5=3,
            ),
        )

        summary = await stats_service.build_summary(session, user.id)

        assert summary.entries_count_last_7_days == 3
        assert "Power Nap 15 min" in summary.most_used_modes
        assert summary.average_sleep_quality_last_7_days == 3.7
        assert summary.pattern_insights

    await engine.dispose()
