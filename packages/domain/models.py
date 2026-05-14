from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class SleepMode(StrEnum):
    NIGHT_SLEEP = "night_sleep"
    DAY_REST = "day_rest"
    POWER_NAP = "power_nap"
    WAKE_CHECKIN = "wake_checkin"
    BEDTIME_PLANNING = "bedtime_planning"
    MEDITATION = "meditation"
    QUICK_SLEEP_TECHNIQUE = "quick_sleep_technique"
    GOOD_WAKE_TECHNIQUE = "good_wake_technique"


class RecommendationMode(StrEnum):
    ULTRA_SHORT_WIND_DOWN = "ultra_short_wind_down"
    SHORT_WIND_DOWN = "short_wind_down"
    STANDARD_WIND_DOWN = "standard_wind_down"
    CALM_NIGHT_PROTOCOL = "calm_night_protocol"
    STRESS_DOWN_PROTOCOL = "stress_down_protocol"
    LOW_ENERGY_GENTLE_SLEEP = "low_energy_gentle_sleep"
    LATE_NIGHT_QUICK_SHUTDOWN = "late_night_quick_shutdown"
    RECOVERY_BREAK = "recovery_break"
    GUIDED_NAP_ATTEMPT = "guided_nap_attempt"
    LONG_REST_SESSION = "long_rest_session"
    POWER_NAP_10 = "power_nap_10"
    POWER_NAP_15 = "power_nap_15"
    POWER_NAP_20 = "power_nap_20"
    BEDTIME_PLAN = "bedtime_plan"
    SLEEP_DEBT_RECOVERY_PLAN = "sleep_debt_recovery_plan"
    MEDITATION_5 = "meditation_5"
    MEDITATION_10 = "meditation_10"
    MEDITATION_15 = "meditation_15"
    QUICK_SLEEP_BREATHING = "quick_sleep_breathing"
    QUICK_SLEEP_BODY_SCAN = "quick_sleep_body_scan"
    QUICK_SLEEP_COGNITIVE_SHUFFLE = "quick_sleep_cognitive_shuffle"
    GOOD_WAKE_GENTLE = "good_wake_gentle"
    GOOD_WAKE_ENERGIZE = "good_wake_energize"


class AudioType(StrEnum):
    SILENCE = "silence"
    RAIN = "rain"
    FOREST = "forest"
    PINK_NOISE = "pink_noise"
    WHITE_NOISE = "white_noise"
    SOFT_MULTIAUDIO = "soft_multiaudio"
    GUIDED_BREATHING_VOICE = "guided_breathing_voice"
    GUIDED_TEXT = "guided_text"
    BREATHING_ONLY = "breathing_only"
    NO_AUDIO = "no_audio"


class AlarmStatus(StrEnum):
    SCHEDULED = "scheduled"
    FIRING = "firing"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    FAILED = "failed"
    CANCELED = "canceled"


class WakeIntensity(StrEnum):
    SOFT = "soft"
    NORMAL = "normal"
    HARD = "hard"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    GRACE = "grace"
    CANCELED = "canceled"
    EXPIRED = "expired"


class BillingProviderName(StrEnum):
    MOCK = "mock"
    TELEGRAM_STARS = "telegram_stars"


class ConsentType(StrEnum):
    CORE = "core"
    PRIVACY = "privacy"
    MARKETING = "marketing"


class AnalyticsEventName(StrEnum):
    STARTED_FLOW = "started_flow"
    COMPLETED_FLOW = "completed_flow"
    ABANDONED_FLOW = "abandoned_flow"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    RECOMMENDATION_FOLLOWED = "recommendation_followed"
    ALARM_CREATED = "alarm_created"
    ALARM_DISMISSED = "alarm_dismissed"
    ALARM_FAILED = "alarm_failed"
    WAKE_CHECKIN_COMPLETED = "wake_checkin_completed"
    PREMIUM_SCREEN_VIEWED = "premium_screen_viewed"
    PAYWALL_SHOWN = "paywall_shown"
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_CANCELED = "subscription_canceled"


@dataclass(frozen=True)
class SleepRequest:
    user_id: UUID
    mode: SleepMode
    slept_last_night_minutes: int
    quality: int
    sleepiness: int
    stress: int
    free_minutes: int
    needs_alarm: bool
    preferred_audio: AudioType
    created_at: datetime
    timezone: str = "UTC"
    fully_switch_off: bool = True
    goal: str | None = None


@dataclass(frozen=True)
class SleepEntry:
    user_id: UUID
    mode: SleepMode
    duration_minutes: int
    quality: int
    post_wake_feeling: int
    helpfulness: int
    audio_used: AudioType
    created_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class DecisionTraceItem:
    rule: str
    reason: str
    weight: int = 1


@dataclass(frozen=True)
class Recommendation:
    id: UUID
    user_id: UUID
    request_mode: SleepMode
    recommended_mode: RecommendationMode
    duration_minutes: int
    steps: tuple[str, ...]
    audio: AudioType
    follow_up_minutes: int | None
    should_create_alarm: bool
    decision_trace: tuple[DecisionTraceItem, ...]
    disclaimer: str
    created_at: datetime
    snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationFeedback:
    recommendation_id: UUID
    user_id: UUID
    helpfulness: int
    note: str | None
    created_at: datetime


@dataclass(frozen=True)
class Alarm:
    id: UUID
    user_id: UUID
    due_at: datetime
    timezone: str
    status: AlarmStatus
    wake_intensity: WakeIntensity
    dismiss_code: str
    max_repeats: int
    repeats_done: int
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True)
class SubscriptionPlan:
    code: str
    title: str
    price_minor: int
    currency: str
    period_days: int
    trial_days: int
    features: frozenset[str]


@dataclass(frozen=True)
class Subscription:
    id: UUID
    user_id: UUID
    plan_code: str
    status: SubscriptionStatus
    provider: BillingProviderName
    current_period_end: datetime
    created_at: datetime
    canceled_at: datetime | None = None


@dataclass(frozen=True)
class PaymentIntent:
    id: UUID
    user_id: UUID
    plan_code: str
    provider: BillingProviderName
    amount_minor: int
    currency: str
    status: str
    payment_url: str
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True)
class AnalyticsEvent:
    id: UUID
    user_id: UUID | None
    name: AnalyticsEventName
    occurred_at: datetime
    properties: dict[str, Any]


@dataclass(frozen=True)
class UserPreferences:
    timezone: str = "UTC"
    language: str = "ru"
    audio_preferences: tuple[AudioType, ...] = (AudioType.SILENCE, AudioType.RAIN)
    disliked_audio: tuple[AudioType, ...] = ()
    default_nap_duration: int = 15
    wake_time: time | None = None
    target_sleep_minutes: int = 480
    dnd_start: time | None = None
    dnd_end: time | None = None
    reminders_enabled: bool = True
    analytics_enabled: bool = True
    marketing_consent: bool = False


def new_uuid() -> UUID:
    return uuid4()
