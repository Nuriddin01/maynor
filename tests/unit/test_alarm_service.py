from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.domain.alarms import AlarmService, InMemoryAlarmStore
from packages.domain.models import AlarmStatus, WakeIntensity, new_uuid


def test_alarm_creation_is_idempotent() -> None:
    store = InMemoryAlarmStore()
    service = AlarmService(store)
    user_id = new_uuid()
    now = datetime.now(timezone.utc)

    first = service.create_relative(user_id, 15, "UTC", WakeIntensity.NORMAL, now, "same-key")
    second = service.create_relative(user_id, 15, "UTC", WakeIntensity.NORMAL, now, "same-key")

    assert first.id == second.id


def test_alarm_in_the_past_rejected() -> None:
    service = AlarmService(InMemoryAlarmStore())
    user_id = new_uuid()
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        service.create_at(user_id, now - timedelta(minutes=1), "UTC", WakeIntensity.NORMAL, now, "past")


def test_due_alarm_claimed_once() -> None:
    service = AlarmService(InMemoryAlarmStore())
    user_id = new_uuid()
    now = datetime.now(timezone.utc)
    alarm = service.create_relative(user_id, 1, "UTC", WakeIntensity.NORMAL, now, "due")

    first = service.claim_due(now + timedelta(minutes=2))
    second = service.claim_due(now + timedelta(minutes=2))

    assert [item.id for item in first] == [alarm.id]
    assert second == ()
    assert first[0].status == AlarmStatus.FIRING


def test_dismiss_requires_code() -> None:
    service = AlarmService(InMemoryAlarmStore())
    user_id = new_uuid()
    now = datetime.now(timezone.utc)
    alarm = service.create_relative(user_id, 1, "UTC", WakeIntensity.NORMAL, now, "dismiss")

    with pytest.raises(ValueError):
        service.dismiss(alarm.id, "0000")

    dismissed = service.dismiss(alarm.id, alarm.dismiss_code)
    assert dismissed.status == AlarmStatus.DISMISSED
