from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db import create_engine, init_db
from app.models import Alarm, User
from app.services.alarm_service import AlarmService


class DummyScheduler:
    def __init__(self) -> None:
        self.scheduled = []
        self.removed = []

    def schedule_alarm(self, alarm_id: int, run_at: datetime) -> None:
        self.scheduled.append((alarm_id, run_at))

    def remove_alarm(self, alarm_id: int) -> None:
        self.removed.append(alarm_id)


def test_generate_alarm_code_length() -> None:
    code = AlarmService.generate_code(6)
    assert len(code) == 6 and code.isdigit()


@pytest.mark.asyncio
async def test_stop_alarm_success_and_fail(tmp_path) -> None:
    db_path = tmp_path / "alarm.db"
    settings = Settings(database_url=f"sqlite+aiosqlite:///{db_path}")
    engine = create_engine(settings)
    await init_db(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    scheduler = DummyScheduler()
    service = AlarmService(settings, scheduler)

    async with factory() as session:
        user = User(telegram_id=999)
        session.add(user)
        await session.flush()
        alarm = Alarm(
            user_id=user.id,
            alarm_time=datetime.now(timezone.utc) + timedelta(minutes=5),
            code="1234",
            repeat_attempts=0,
            max_repeat_attempts=3,
            is_active=True,
        )
        session.add(alarm)
        await session.commit()

        fail = await service.confirm_alarm_stop(session, 999, "0000")
        assert fail.stopped is False

        ok = await service.confirm_alarm_stop(session, 999, "1234")
        assert ok.stopped is True

    await engine.dispose()
