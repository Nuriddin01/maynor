from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.domain.models import AudioType, SleepEntry, SleepMode, new_uuid
from packages.domain.stats import StatsService


def test_summary_calculates_basic_metrics() -> None:
    user_id = new_uuid()
    now = datetime.now(timezone.utc)
    entries = (
        SleepEntry(user_id, SleepMode.NIGHT_SLEEP, 390, 3, 4, 4, AudioType.SILENCE, now - timedelta(days=1)),
        SleepEntry(user_id, SleepMode.NIGHT_SLEEP, 450, 5, 5, 5, AudioType.RAIN, now),
    )

    summary = StatsService().summarize(entries, now, 7, started_flows=4)

    assert summary.entries_count == 2
    assert summary.average_duration == 420
    assert summary.average_quality == 4
    assert summary.possible_sleep_debt_minutes == 30
    assert summary.completion_rate == 0.5
