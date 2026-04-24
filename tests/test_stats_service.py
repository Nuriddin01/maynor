from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db import create_engine, init_db
from app.models import SleepEntry, User
from app.services.stats_service import StatsService
from app.utils.time_utils import utc_now


@pytest.mark.asyncio
async def test_stats_average_duration(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    settings = Settings(database_url=f"sqlite+aiosqlite:///{db_path}")
    engine = create_engine(settings)
    await init_db(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = User(telegram_id=123)
        session.add(user)
        await session.flush()
        session.add_all(
            [
                SleepEntry(user_id=user.id, mode="power_nap_10", duration_minutes=10, created_at=utc_now() - timedelta(days=1)),
                SleepEntry(user_id=user.id, mode="power_nap_20", duration_minutes=20, created_at=utc_now() - timedelta(days=2)),
            ]
        )
        await session.commit()
        summary = await StatsService().build_summary(session, user.id)
        assert summary.average_duration_minutes_last_7_days == 15.0

    await engine.dispose()
