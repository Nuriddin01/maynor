from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from packages.domain.models import AnalyticsEvent, AnalyticsEventName, new_uuid


class AnalyticsStore(Protocol):
    def add_event(self, event: AnalyticsEvent) -> None: ...
    def events_since(self, since: datetime) -> tuple[AnalyticsEvent, ...]: ...


@dataclass
class AnalyticsMemoryStore:
    events: list[AnalyticsEvent] = field(default_factory=list)

    def add_event(self, event: AnalyticsEvent) -> None:
        self.events.append(event)

    def events_since(self, since: datetime) -> tuple[AnalyticsEvent, ...]:
        return tuple(event for event in self.events if event.occurred_at >= since)


class AnalyticsService:
    def __init__(self, store: AnalyticsStore | None = None) -> None:
        self._store = store or AnalyticsMemoryStore()

    def track(self, name: AnalyticsEventName, user_id: UUID | None, properties: dict[str, object] | None = None) -> AnalyticsEvent:
        event = AnalyticsEvent(
            id=new_uuid(),
            user_id=user_id,
            name=name,
            occurred_at=datetime.now(timezone.utc),
            properties=dict(properties or {}),
        )
        self._store.add_event(event)
        return event

    def summary(self, days: int = 30) -> dict[str, object]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        scoped = list(self._store.events_since(since))
        users = {event.user_id for event in scoped if event.user_id is not None}
        counts = Counter(event.name.value for event in scoped)
        started = counts.get(AnalyticsEventName.STARTED_FLOW.value, 0)
        completed = counts.get(AnalyticsEventName.COMPLETED_FLOW.value, 0)
        premium_views = counts.get(AnalyticsEventName.PREMIUM_SCREEN_VIEWED.value, 0)
        subscriptions = counts.get(AnalyticsEventName.SUBSCRIPTION_STARTED.value, 0)
        return {
            "days": days,
            "events": len(scoped),
            "active_users_basis": len(users),
            "counts": dict(counts),
            "flow_completion_rate": None if started == 0 else round(completed / started, 4),
            "premium_conversion_basis": None if premium_views == 0 else round(subscriptions / premium_views, 4),
        }
