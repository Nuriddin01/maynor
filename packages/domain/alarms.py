from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from packages.domain.models import Alarm, AlarmStatus, WakeIntensity, new_uuid


class AlarmStore(Protocol):
    def find_by_idempotency_key(self, key: str) -> Alarm | None: ...
    def save(self, alarm: Alarm) -> Alarm: ...
    def due(self, now: datetime, limit: int) -> tuple[Alarm, ...]: ...
    def update(self, alarm: Alarm) -> Alarm: ...
    def get(self, alarm_id: UUID) -> Alarm | None: ...


class InMemoryAlarmStore:
    def __init__(self) -> None:
        self._items: dict[UUID, Alarm] = {}
        self._keys: dict[str, UUID] = {}

    def find_by_idempotency_key(self, key: str) -> Alarm | None:
        alarm_id = self._keys.get(key)
        return self._items.get(alarm_id) if alarm_id else None

    def save(self, alarm: Alarm) -> Alarm:
        existing = self.find_by_idempotency_key(alarm.idempotency_key)
        if existing:
            return existing
        self._items[alarm.id] = alarm
        self._keys[alarm.idempotency_key] = alarm.id
        return alarm

    def due(self, now: datetime, limit: int) -> tuple[Alarm, ...]:
        alarms = [alarm for alarm in self._items.values() if alarm.status == AlarmStatus.SCHEDULED and alarm.due_at <= now]
        alarms.sort(key=lambda alarm: alarm.due_at)
        return tuple(alarms[:limit])

    def update(self, alarm: Alarm) -> Alarm:
        self._items[alarm.id] = alarm
        self._keys[alarm.idempotency_key] = alarm.id
        return alarm

    def get(self, alarm_id: UUID) -> Alarm | None:
        return self._items.get(alarm_id)


class AlarmService:
    def __init__(self, store: AlarmStore) -> None:
        self._store = store

    def create_relative(
        self,
        user_id: UUID,
        minutes: int,
        timezone_name: str,
        wake_intensity: WakeIntensity,
        now: datetime,
        idempotency_key: str,
    ) -> Alarm:
        if minutes <= 0:
            raise ValueError("alarm minutes must be positive")
        due_at = now + timedelta(minutes=minutes)
        return self.create_at(user_id, due_at, timezone_name, wake_intensity, now, idempotency_key)

    def create_at(
        self,
        user_id: UUID,
        due_at: datetime,
        timezone_name: str,
        wake_intensity: WakeIntensity,
        now: datetime,
        idempotency_key: str,
    ) -> Alarm:
        if due_at <= now:
            raise ValueError("alarm time must be in the future")
        existing = self._store.find_by_idempotency_key(idempotency_key)
        if existing:
            return existing
        dismiss_code = str(abs(hash((str(user_id), due_at.isoformat(), idempotency_key))) % 9000 + 1000)
        alarm = Alarm(
            id=new_uuid(),
            user_id=user_id,
            due_at=due_at.astimezone(timezone.utc),
            timezone=timezone_name,
            status=AlarmStatus.SCHEDULED,
            wake_intensity=wake_intensity,
            dismiss_code=dismiss_code,
            max_repeats=3,
            repeats_done=0,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        return self._store.save(alarm)

    def claim_due(self, now: datetime, limit: int = 100) -> tuple[Alarm, ...]:
        claimed: list[Alarm] = []
        for alarm in self._store.due(now, limit):
            if alarm.status != AlarmStatus.SCHEDULED:
                continue
            updated = replace(alarm, status=AlarmStatus.FIRING)
            claimed.append(self._store.update(updated))
        return tuple(claimed)

    def dismiss(self, alarm_id: UUID, code: str | None = None) -> Alarm:
        alarm = self._require_alarm(alarm_id)
        if code is not None and code != alarm.dismiss_code:
            raise ValueError("invalid dismiss code")
        updated = replace(alarm, status=AlarmStatus.DISMISSED)
        return self._store.update(updated)

    def mark_failed_or_repeat(self, alarm_id: UUID, now: datetime) -> Alarm:
        alarm = self._require_alarm(alarm_id)
        if alarm.repeats_done >= alarm.max_repeats:
            return self._store.update(replace(alarm, status=AlarmStatus.FAILED))
        next_due = now + timedelta(minutes=2)
        return self._store.update(
            replace(alarm, status=AlarmStatus.SCHEDULED, due_at=next_due, repeats_done=alarm.repeats_done + 1)
        )

    def cancel(self, alarm_id: UUID) -> Alarm:
        alarm = self._require_alarm(alarm_id)
        return self._store.update(replace(alarm, status=AlarmStatus.CANCELED))

    def _require_alarm(self, alarm_id: UUID) -> Alarm:
        alarm = self._store.get(alarm_id)
        if alarm is None:
            raise KeyError("alarm not found")
        return alarm
