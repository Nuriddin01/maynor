from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.domain.consent import ConsentVersion, UserConsent
from packages.domain.models import (
    Alarm,
    AlarmStatus,
    AnalyticsEvent,
    AnalyticsEventName,
    AudioType,
    BillingProviderName,
    ConsentType,
    DecisionTraceItem,
    PaymentIntent,
    Recommendation,
    RecommendationFeedback,
    RecommendationMode,
    SleepEntry,
    SleepMode,
    Subscription,
    SubscriptionStatus,
    UserPreferences,
    WakeIntensity,
)
from packages.services.memory import UserRecord


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def dump_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _time_to_text(value: time | None) -> str | None:
    return value.isoformat(timespec="minutes") if value else None


def _time_from_text(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def preferences_to_json(preferences: UserPreferences) -> str:
    return dump_json(
        {
            "timezone": preferences.timezone,
            "language": preferences.language,
            "audio_preferences": [item.value for item in preferences.audio_preferences],
            "disliked_audio": [item.value for item in preferences.disliked_audio],
            "default_nap_duration": preferences.default_nap_duration,
            "wake_time": _time_to_text(preferences.wake_time),
            "target_sleep_minutes": preferences.target_sleep_minutes,
            "dnd_start": _time_to_text(preferences.dnd_start),
            "dnd_end": _time_to_text(preferences.dnd_end),
            "reminders_enabled": preferences.reminders_enabled,
            "analytics_enabled": preferences.analytics_enabled,
            "marketing_consent": preferences.marketing_consent,
        }
    )


def preferences_from_json(value: str | None) -> UserPreferences:
    raw = load_json(value, {})
    return UserPreferences(
        timezone=raw.get("timezone", "UTC"),
        language=raw.get("language", "ru"),
        audio_preferences=tuple(AudioType(item) for item in raw.get("audio_preferences", [AudioType.SILENCE.value, AudioType.RAIN.value])),
        disliked_audio=tuple(AudioType(item) for item in raw.get("disliked_audio", [])),
        default_nap_duration=int(raw.get("default_nap_duration", 15)),
        wake_time=_time_from_text(raw.get("wake_time")),
        target_sleep_minutes=int(raw.get("target_sleep_minutes", 480)),
        dnd_start=_time_from_text(raw.get("dnd_start")),
        dnd_end=_time_from_text(raw.get("dnd_end")),
        reminders_enabled=bool(raw.get("reminders_enabled", True)),
        analytics_enabled=bool(raw.get("analytics_enabled", True)),
        marketing_consent=bool(raw.get("marketing_consent", False)),
    )


class SQLiteConnectionMixin:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    created_at TEXT NOT NULL,
                    preferences_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_consents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    consent_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    accepted_at TEXT NOT NULL,
                    UNIQUE(user_id, consent_type, version)
                );

                CREATE TABLE IF NOT EXISTS sleep_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    mode TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    quality INTEGER NOT NULL,
                    post_wake_feeling INTEGER NOT NULL,
                    helpfulness INTEGER NOT NULL,
                    audio_used TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    note TEXT
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    request_mode TEXT NOT NULL,
                    recommended_mode TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    steps_json TEXT NOT NULL,
                    audio TEXT NOT NULL,
                    follow_up_minutes INTEGER,
                    should_create_alarm INTEGER NOT NULL,
                    decision_trace_json TEXT NOT NULL,
                    disclaimer TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id TEXT NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    helpfulness INTEGER NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recommendation_feedback_user ON recommendation_feedback(user_id, created_at);

                CREATE TABLE IF NOT EXISTS alarms (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    due_at TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    wake_intensity TEXT NOT NULL,
                    dismiss_code TEXT NOT NULL,
                    max_repeats INTEGER NOT NULL,
                    repeats_done INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alarms_due ON alarms(status, due_at);

                CREATE TABLE IF NOT EXISTS analytics_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    name TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analytics_time ON analytics_events(occurred_at);

                CREATE TABLE IF NOT EXISTS payment_intents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    plan_code TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payment_url TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    plan_code TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    current_period_end TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    canceled_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id TEXT,
                    at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )


class SQLiteAppStore(SQLiteConnectionMixin):
    def upsert_user(self, telegram_id: int, username: str | None = None) -> UserRecord:
        existing = self.get_user_by_telegram(telegram_id)
        if existing:
            if username and username != existing.username:
                with self.connect() as connection:
                    connection.execute("UPDATE users SET username = ? WHERE id = ?", (username, str(existing.id)))
                return replace(existing, username=username)
            return existing
        from packages.domain.models import new_uuid

        user = UserRecord(
            id=new_uuid(),
            telegram_id=telegram_id,
            username=username,
            created_at=datetime.now(timezone.utc),
            preferences=UserPreferences(),
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO users(id, telegram_id, username, created_at, preferences_json) VALUES (?, ?, ?, ?, ?)",
                (str(user.id), user.telegram_id, user.username, dump_dt(user.created_at), preferences_to_json(user.preferences)),
            )
        return user

    def get_user_by_telegram(self, telegram_id: int) -> UserRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        return self._row_to_user(row) if row else None

    def update_preferences(self, user_id: UUID, preferences: UserPreferences) -> UserRecord:
        with self.connect() as connection:
            connection.execute("UPDATE users SET preferences_json = ? WHERE id = ?", (preferences_to_json(preferences), str(user_id)))
        user = self.get_user_by_id(user_id)
        if user is None:
            raise KeyError("user not found")
        return user

    @property
    def users_by_id(self) -> dict[UUID, UserRecord]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        users = [self._row_to_user(row) for row in rows]
        return {user.id: user for user in users if user is not None}

    @property
    def users_by_telegram(self) -> dict[int, UserRecord]:
        return {user.telegram_id: user for user in self.users_by_id.values()}

    @property
    def entries(self) -> dict[UUID, list[SleepEntry]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM sleep_entries ORDER BY created_at").fetchall()
        result: dict[UUID, list[SleepEntry]] = {}
        for row in rows:
            entry = self._row_to_sleep_entry(row)
            result.setdefault(entry.user_id, []).append(entry)
        return result

    @property
    def recommendations(self) -> dict[UUID, list[Recommendation]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM recommendations ORDER BY created_at").fetchall()
        result: dict[UUID, list[Recommendation]] = {}
        for row in rows:
            recommendation = self._row_to_recommendation(row)
            result.setdefault(recommendation.user_id, []).append(recommendation)
        return result

    @property
    def recommendation_feedback(self) -> dict[UUID, list[RecommendationFeedback]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM recommendation_feedback ORDER BY created_at").fetchall()
        result: dict[UUID, list[RecommendationFeedback]] = {}
        for row in rows:
            feedback = self._row_to_recommendation_feedback(row)
            result.setdefault(feedback.user_id, []).append(feedback)
        return result

    @property
    def consents(self) -> dict[UUID, list[UserConsent]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM user_consents ORDER BY accepted_at").fetchall()
        result: dict[UUID, list[UserConsent]] = {}
        for row in rows:
            accepted_at = parse_dt(row["accepted_at"])
            assert accepted_at is not None
            consent = UserConsent(
                user_id=UUID(row["user_id"]),
                type=ConsentType(row["consent_type"]),
                version=row["version"],
                accepted=bool(row["accepted"]),
                accepted_at=accepted_at,
            )
            result.setdefault(consent.user_id, []).append(consent)
        return result

    @property
    def audit_logs(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 500").fetchall()
        return [
            {
                "id": row["id"],
                "action": row["action"],
                "user_id": row["user_id"],
                "at": row["at"],
                "metadata": load_json(row["metadata_json"], {}),
            }
            for row in rows
        ]

    def add_entry(self, entry: SleepEntry) -> SleepEntry:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sleep_entries(user_id, mode, duration_minutes, quality, post_wake_feeling, helpfulness, audio_used, created_at, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(entry.user_id),
                    entry.mode.value,
                    entry.duration_minutes,
                    entry.quality,
                    entry.post_wake_feeling,
                    entry.helpfulness,
                    entry.audio_used.value,
                    dump_dt(entry.created_at),
                    entry.note,
                ),
            )
        return entry

    def add_recommendation(self, recommendation: Recommendation) -> Recommendation:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO recommendations(
                    id, user_id, request_mode, recommended_mode, duration_minutes, steps_json, audio,
                    follow_up_minutes, should_create_alarm, decision_trace_json, disclaimer, created_at, snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(recommendation.id),
                    str(recommendation.user_id),
                    recommendation.request_mode.value,
                    recommendation.recommended_mode.value,
                    recommendation.duration_minutes,
                    dump_json(list(recommendation.steps)),
                    recommendation.audio.value,
                    recommendation.follow_up_minutes,
                    int(recommendation.should_create_alarm),
                    dump_json([item.__dict__ for item in recommendation.decision_trace]),
                    recommendation.disclaimer,
                    dump_dt(recommendation.created_at),
                    dump_json(recommendation.snapshot),
                ),
            )
        return recommendation

    def add_recommendation_feedback(self, feedback: RecommendationFeedback) -> RecommendationFeedback:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO recommendation_feedback(recommendation_id, user_id, helpfulness, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(feedback.recommendation_id),
                    str(feedback.user_id),
                    feedback.helpfulness,
                    feedback.note,
                    dump_dt(feedback.created_at),
                ),
            )
        return feedback

    def accept_required_consents(self, user_id: UUID, versions: tuple[ConsentVersion, ...]) -> None:
        now = datetime.now(timezone.utc)
        with self.connect() as connection:
            for version in versions:
                if version.type == ConsentType.MARKETING:
                    continue
                connection.execute(
                    """
                    INSERT OR REPLACE INTO user_consents(user_id, consent_type, version, accepted, accepted_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(user_id), version.type.value, version.version, 1, dump_dt(now)),
                )

    def export_user(self, user_id: UUID) -> dict[str, object]:
        user = self.get_user_by_id(user_id)
        if user is None:
            raise KeyError("user not found")
        return {
            "user": {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "username": user.username,
                "created_at": user.created_at.isoformat(),
                "preferences": json.loads(preferences_to_json(user.preferences)),
            },
            "sleep_entries": [self._sleep_entry_to_dict(entry) for entry in self.entries.get(user_id, [])],
            "recommendations": [self._recommendation_to_dict(item) for item in self.recommendations.get(user_id, [])],
            "recommendation_feedback": [self._recommendation_feedback_to_dict(item) for item in self.recommendation_feedback.get(user_id, [])],
            "consents": [self._consent_to_dict(item) for item in self.consents.get(user_id, [])],
        }

    def delete_user(self, user_id: UUID) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM users WHERE id = ?", (str(user_id),))
            connection.execute(
                "INSERT INTO audit_logs(action, user_id, at, metadata_json) VALUES (?, ?, ?, ?)",
                ("delete_user", str(user_id), dump_dt(datetime.now(timezone.utc)), dump_json({})),
            )

    def _row_to_user(self, row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        created_at = parse_dt(row["created_at"])
        assert created_at is not None
        return UserRecord(
            id=UUID(row["id"]),
            telegram_id=int(row["telegram_id"]),
            username=row["username"],
            created_at=created_at,
            preferences=preferences_from_json(row["preferences_json"]),
        )

    def _row_to_sleep_entry(self, row: sqlite3.Row) -> SleepEntry:
        created_at = parse_dt(row["created_at"])
        assert created_at is not None
        return SleepEntry(
            user_id=UUID(row["user_id"]),
            mode=SleepMode(row["mode"]),
            duration_minutes=int(row["duration_minutes"]),
            quality=int(row["quality"]),
            post_wake_feeling=int(row["post_wake_feeling"]),
            helpfulness=int(row["helpfulness"]),
            audio_used=AudioType(row["audio_used"]),
            created_at=created_at,
            note=row["note"],
        )

    def _row_to_recommendation(self, row: sqlite3.Row) -> Recommendation:
        created_at = parse_dt(row["created_at"])
        assert created_at is not None
        return Recommendation(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            request_mode=SleepMode(row["request_mode"]),
            recommended_mode=RecommendationMode(row["recommended_mode"]),
            duration_minutes=int(row["duration_minutes"]),
            steps=tuple(load_json(row["steps_json"], [])),
            audio=AudioType(row["audio"]),
            follow_up_minutes=row["follow_up_minutes"],
            should_create_alarm=bool(row["should_create_alarm"]),
            decision_trace=tuple(
                DecisionTraceItem(item["rule"], item["reason"], int(item.get("weight", 1)))
                for item in load_json(row["decision_trace_json"], [])
            ),
            disclaimer=row["disclaimer"],
            created_at=created_at,
            snapshot=load_json(row["snapshot_json"], {}),
        )

    def _row_to_recommendation_feedback(self, row: sqlite3.Row) -> RecommendationFeedback:
        created_at = parse_dt(row["created_at"])
        assert created_at is not None
        return RecommendationFeedback(
            recommendation_id=UUID(row["recommendation_id"]),
            user_id=UUID(row["user_id"]),
            helpfulness=int(row["helpfulness"]),
            note=row["note"],
            created_at=created_at,
        )

    def _sleep_entry_to_dict(self, entry: SleepEntry) -> dict[str, object]:
        return {
            "user_id": str(entry.user_id),
            "mode": entry.mode.value,
            "duration_minutes": entry.duration_minutes,
            "quality": entry.quality,
            "post_wake_feeling": entry.post_wake_feeling,
            "helpfulness": entry.helpfulness,
            "audio_used": entry.audio_used.value,
            "created_at": entry.created_at.isoformat(),
            "note": entry.note,
        }

    def _recommendation_to_dict(self, recommendation: Recommendation) -> dict[str, object]:
        return {
            "id": str(recommendation.id),
            "user_id": str(recommendation.user_id),
            "request_mode": recommendation.request_mode.value,
            "recommended_mode": recommendation.recommended_mode.value,
            "duration_minutes": recommendation.duration_minutes,
            "steps": list(recommendation.steps),
            "audio": recommendation.audio.value,
            "follow_up_minutes": recommendation.follow_up_minutes,
            "should_create_alarm": recommendation.should_create_alarm,
            "decision_trace": [item.__dict__ for item in recommendation.decision_trace],
            "disclaimer": recommendation.disclaimer,
            "created_at": recommendation.created_at.isoformat(),
            "snapshot": recommendation.snapshot,
        }

    def _recommendation_feedback_to_dict(self, feedback: RecommendationFeedback) -> dict[str, object]:
        return {
            "recommendation_id": str(feedback.recommendation_id),
            "user_id": str(feedback.user_id),
            "helpfulness": feedback.helpfulness,
            "note": feedback.note,
            "created_at": feedback.created_at.isoformat(),
        }

    def _consent_to_dict(self, consent: UserConsent) -> dict[str, object]:
        return {
            "user_id": str(consent.user_id),
            "type": consent.type.value,
            "version": consent.version,
            "accepted": consent.accepted,
            "accepted_at": consent.accepted_at.isoformat(),
        }


class SQLiteAlarmStore(SQLiteConnectionMixin):
    def find_by_idempotency_key(self, key: str) -> Alarm | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM alarms WHERE idempotency_key = ?", (key,)).fetchone()
        return self._row_to_alarm(row) if row else None

    def save(self, alarm: Alarm) -> Alarm:
        existing = self.find_by_idempotency_key(alarm.idempotency_key)
        if existing:
            return existing
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO alarms(
                    id, user_id, due_at, timezone, status, wake_intensity, dismiss_code,
                    max_repeats, repeats_done, idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._alarm_values(alarm),
            )
        return alarm

    def due(self, now: datetime, limit: int) -> tuple[Alarm, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alarms WHERE status = ? AND due_at <= ? ORDER BY due_at LIMIT ?",
                (AlarmStatus.SCHEDULED.value, dump_dt(now), limit),
            ).fetchall()
        return tuple(self._row_to_alarm(row) for row in rows)

    def update(self, alarm: Alarm) -> Alarm:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE alarms SET
                    user_id = ?, due_at = ?, timezone = ?, status = ?, wake_intensity = ?, dismiss_code = ?,
                    max_repeats = ?, repeats_done = ?, idempotency_key = ?, created_at = ?
                WHERE id = ?
                """,
                (
                    str(alarm.user_id),
                    dump_dt(alarm.due_at),
                    alarm.timezone,
                    alarm.status.value,
                    alarm.wake_intensity.value,
                    alarm.dismiss_code,
                    alarm.max_repeats,
                    alarm.repeats_done,
                    alarm.idempotency_key,
                    dump_dt(alarm.created_at),
                    str(alarm.id),
                ),
            )
        return alarm

    def get(self, alarm_id: UUID) -> Alarm | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM alarms WHERE id = ?", (str(alarm_id),)).fetchone()
        return self._row_to_alarm(row) if row else None

    def all(self) -> tuple[Alarm, ...]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM alarms ORDER BY due_at DESC").fetchall()
        return tuple(self._row_to_alarm(row) for row in rows)

    @property
    def _items(self) -> dict[UUID, Alarm]:
        return {alarm.id: alarm for alarm in self.all()}

    def _alarm_values(self, alarm: Alarm) -> tuple[object, ...]:
        return (
            str(alarm.id),
            str(alarm.user_id),
            dump_dt(alarm.due_at),
            alarm.timezone,
            alarm.status.value,
            alarm.wake_intensity.value,
            alarm.dismiss_code,
            alarm.max_repeats,
            alarm.repeats_done,
            alarm.idempotency_key,
            dump_dt(alarm.created_at),
        )

    def _row_to_alarm(self, row: sqlite3.Row) -> Alarm:
        due_at = parse_dt(row["due_at"])
        created_at = parse_dt(row["created_at"])
        assert due_at is not None and created_at is not None
        return Alarm(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            due_at=due_at,
            timezone=row["timezone"],
            status=AlarmStatus(row["status"]),
            wake_intensity=WakeIntensity(row["wake_intensity"]),
            dismiss_code=row["dismiss_code"],
            max_repeats=int(row["max_repeats"]),
            repeats_done=int(row["repeats_done"]),
            idempotency_key=row["idempotency_key"],
            created_at=created_at,
        )


class SQLiteAnalyticsStore(SQLiteConnectionMixin):
    def add_event(self, event: AnalyticsEvent) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO analytics_events(id, user_id, name, occurred_at, properties_json) VALUES (?, ?, ?, ?, ?)",
                (str(event.id), str(event.user_id) if event.user_id else None, event.name.value, dump_dt(event.occurred_at), dump_json(event.properties)),
            )

    def events_since(self, since: datetime) -> tuple[AnalyticsEvent, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analytics_events WHERE occurred_at >= ? ORDER BY occurred_at",
                (dump_dt(since),),
            ).fetchall()
        return tuple(self._row_to_event(row) for row in rows)

    @property
    def events(self) -> list[AnalyticsEvent]:
        return list(self.events_since(datetime(1970, 1, 1, tzinfo=timezone.utc)))

    def _row_to_event(self, row: sqlite3.Row) -> AnalyticsEvent:
        occurred_at = parse_dt(row["occurred_at"])
        assert occurred_at is not None
        return AnalyticsEvent(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]) if row["user_id"] else None,
            name=AnalyticsEventName(row["name"]),
            occurred_at=occurred_at,
            properties=load_json(row["properties_json"], {}),
        )


class SQLiteBillingStore(SQLiteConnectionMixin):
    @property
    def payments(self) -> dict[str, PaymentIntent]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM payment_intents").fetchall()
        return {row["idempotency_key"]: self._row_to_payment(row) for row in rows}

    @property
    def subscriptions(self) -> dict[UUID, Subscription]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM subscriptions").fetchall()
        return {UUID(row["user_id"]): self._row_to_subscription(row) for row in rows}

    def get_payment(self, idempotency_key: str) -> PaymentIntent | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM payment_intents WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        return self._row_to_payment(row) if row else None

    def save_payment(self, intent: PaymentIntent) -> PaymentIntent:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO payment_intents(
                    id, user_id, plan_code, provider, amount_minor, currency, status, payment_url, idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(intent.id),
                    str(intent.user_id),
                    intent.plan_code,
                    intent.provider.value,
                    intent.amount_minor,
                    intent.currency,
                    intent.status,
                    intent.payment_url,
                    intent.idempotency_key,
                    dump_dt(intent.created_at),
                ),
            )
        return intent

    def get_subscription(self, user_id: UUID) -> Subscription | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM subscriptions WHERE user_id = ?", (str(user_id),)).fetchone()
        return self._row_to_subscription(row) if row else None

    def save_subscription(self, subscription: Subscription) -> Subscription:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO subscriptions(
                    id, user_id, plan_code, status, provider, current_period_end, created_at, canceled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(subscription.id),
                    str(subscription.user_id),
                    subscription.plan_code,
                    subscription.status.value,
                    subscription.provider.value,
                    dump_dt(subscription.current_period_end),
                    dump_dt(subscription.created_at),
                    dump_dt(subscription.canceled_at),
                ),
            )
        return subscription

    def _row_to_payment(self, row: sqlite3.Row) -> PaymentIntent:
        created_at = parse_dt(row["created_at"])
        assert created_at is not None
        return PaymentIntent(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            plan_code=row["plan_code"],
            provider=BillingProviderName(row["provider"]),
            amount_minor=int(row["amount_minor"]),
            currency=row["currency"],
            status=row["status"],
            payment_url=row["payment_url"],
            idempotency_key=row["idempotency_key"],
            created_at=created_at,
        )

    def _row_to_subscription(self, row: sqlite3.Row) -> Subscription:
        current_period_end = parse_dt(row["current_period_end"])
        created_at = parse_dt(row["created_at"])
        canceled_at = parse_dt(row["canceled_at"])
        assert current_period_end is not None and created_at is not None
        return Subscription(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            plan_code=row["plan_code"],
            status=SubscriptionStatus(row["status"]),
            provider=BillingProviderName(row["provider"]),
            current_period_end=current_period_end,
            created_at=created_at,
            canceled_at=canceled_at,
        )
