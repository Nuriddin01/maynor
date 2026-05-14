from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import UUID

from packages.domain.consent import ConsentVersion, UserConsent
from packages.domain.models import (
    ConsentType,
    Recommendation,
    RecommendationFeedback,
    SleepEntry,
    UserPreferences,
    new_uuid,
)


@dataclass
class UserRecord:
    id: UUID
    telegram_id: int
    username: str | None
    created_at: datetime
    preferences: UserPreferences = field(default_factory=UserPreferences)


class InMemoryAppStore:
    def __init__(self) -> None:
        self.users_by_telegram: dict[int, UserRecord] = {}
        self.users_by_id: dict[UUID, UserRecord] = {}
        self.entries: dict[UUID, list[SleepEntry]] = {}
        self.recommendations: dict[UUID, list[Recommendation]] = {}
        self.recommendation_feedback: dict[UUID, list[RecommendationFeedback]] = {}
        self.consents: dict[UUID, list[UserConsent]] = {}
        self.audit_logs: list[dict[str, object]] = []

    def upsert_user(self, telegram_id: int, username: str | None = None) -> UserRecord:
        existing = self.users_by_telegram.get(telegram_id)
        if existing:
            if username and username != existing.username:
                updated = replace(existing, username=username)
                self.users_by_telegram[telegram_id] = updated
                self.users_by_id[updated.id] = updated
                return updated
            return existing
        user = UserRecord(id=new_uuid(), telegram_id=telegram_id, username=username, created_at=datetime.now(timezone.utc))
        self.users_by_telegram[telegram_id] = user
        self.users_by_id[user.id] = user
        self.entries[user.id] = []
        self.recommendations[user.id] = []
        self.recommendation_feedback[user.id] = []
        self.consents[user.id] = []
        return user

    def update_preferences(self, user_id: UUID, preferences: UserPreferences) -> UserRecord:
        user = self.users_by_id[user_id]
        updated = replace(user, preferences=preferences)
        self.users_by_id[user_id] = updated
        self.users_by_telegram[updated.telegram_id] = updated
        return updated

    def add_entry(self, entry: SleepEntry) -> SleepEntry:
        self.entries.setdefault(entry.user_id, []).append(entry)
        return entry

    def add_recommendation(self, recommendation: Recommendation) -> Recommendation:
        self.recommendations.setdefault(recommendation.user_id, []).append(recommendation)
        return recommendation

    def add_recommendation_feedback(self, feedback: RecommendationFeedback) -> RecommendationFeedback:
        self.recommendation_feedback.setdefault(feedback.user_id, []).append(feedback)
        return feedback

    def accept_required_consents(self, user_id: UUID, versions: tuple[ConsentVersion, ...]) -> None:
        now = datetime.now(timezone.utc)
        existing = self.consents.setdefault(user_id, [])
        for version in versions:
            if version.type == ConsentType.MARKETING:
                continue
            existing.append(UserConsent(user_id, version.type, version.version, True, now))

    def export_user(self, user_id: UUID) -> dict[str, object]:
        user = self.users_by_id[user_id]
        return {
            "user": {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "username": user.username,
                "created_at": user.created_at.isoformat(),
                "preferences": user.preferences.__dict__,
            },
            "sleep_entries": [entry.__dict__ for entry in self.entries.get(user_id, [])],
            "recommendations": [self._recommendation_to_dict(item) for item in self.recommendations.get(user_id, [])],
            "recommendation_feedback": [item.__dict__ for item in self.recommendation_feedback.get(user_id, [])],
            "consents": [item.__dict__ for item in self.consents.get(user_id, [])],
        }

    def delete_user(self, user_id: UUID) -> None:
        user = self.users_by_id.pop(user_id)
        self.users_by_telegram.pop(user.telegram_id, None)
        self.entries.pop(user_id, None)
        self.recommendations.pop(user_id, None)
        self.recommendation_feedback.pop(user_id, None)
        self.consents.pop(user_id, None)
        self.audit_logs.append({"action": "delete_user", "user_id": str(user_id), "at": datetime.now(timezone.utc).isoformat()})

    def _recommendation_to_dict(self, recommendation: Recommendation) -> dict[str, object]:
        return {
            "id": str(recommendation.id),
            "user_id": str(recommendation.user_id),
            "request_mode": recommendation.request_mode.value,
            "recommended_mode": recommendation.recommended_mode.value,
            "duration_minutes": recommendation.duration_minutes,
            "steps": list(recommendation.steps),
            "audio": recommendation.audio.value,
            "created_at": recommendation.created_at.isoformat(),
            "snapshot": recommendation.snapshot,
        }
