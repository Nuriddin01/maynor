from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import create_engine, create_session_factory, init_db
from app.services.alarm_service import AlarmService
from app.services.user_service import UserService


class FakeScheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[int, object]] = []
        self.removed: list[int] = []

    def schedule_alarm(self, alarm_id: int, run_at) -> None:
        self.scheduled.append((alarm_id, run_at))

    def remove_alarm(self, alarm_id: int) -> None:
        self.removed.append(alarm_id)


def make_local_db_path(filename_prefix: str) -> Path:
    runtime_dir = Path(".test_runtime")
    runtime_dir.mkdir(exist_ok=True)
    return runtime_dir / f"{filename_prefix}_{uuid4().hex}.db"


@pytest.mark.asyncio
async def test_create_and_stop_alarm() -> None:
    db_path = make_local_db_path("alarm_test")
    settings = Settings(
        telegram_bot_token="token",
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )
    engine = create_engine(settings)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    scheduler = FakeScheduler()
    alarm_service = AlarmService(settings, scheduler)
    user_service = UserService(settings)

    async with session_factory() as session:  # type: AsyncSession
        user = await user_service.get_or_create_user(session, telegram_id=1001, name="Test User")
        result = await alarm_service.create_alarm_in_minutes(session, user, 15)
        stop_result = await alarm_service.confirm_alarm_stop(session, user.telegram_id, result.code)

        assert result.code.isdigit()
        assert len(result.code) == 4
        assert stop_result.stopped is True
        assert scheduler.scheduled
        assert scheduler.removed == [result.alarm_id]

    await engine.dispose()


@pytest.mark.asyncio
async def test_second_active_alarm_is_rejected() -> None:
    db_path = make_local_db_path("alarm_reject")
    settings = Settings(
        telegram_bot_token="token",
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
    )
    engine = create_engine(settings)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    scheduler = FakeScheduler()
    alarm_service = AlarmService(settings, scheduler)
    user_service = UserService(settings)

    async with session_factory() as session:
        user = await user_service.get_or_create_user(session, telegram_id=2002, name="Alarm User")
        await alarm_service.create_alarm_in_minutes(session, user, 10)
        with pytest.raises(ValueError):
            await alarm_service.create_alarm_in_minutes(session, user, 20)

    await engine.dispose()
