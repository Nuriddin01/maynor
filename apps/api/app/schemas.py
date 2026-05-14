from __future__ import annotations

from datetime import time
from uuid import UUID

from pydantic import BaseModel, Field

from packages.domain.models import AudioType


class StartUserRequest(BaseModel):
    telegram_id: int
    username: str | None = None


class ProfileRequest(BaseModel):
    wake_time: time | None = None
    timezone: str | None = None
    target_sleep_minutes: int | None = Field(default=None, ge=300, le=660)
    default_nap_duration: int | None = Field(default=None, ge=10, le=20)


class RecommendationRequest(BaseModel):
    telegram_id: int
    slept_last_night_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    sleepiness: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    free_minutes: int = Field(ge=1, le=240)
    needs_alarm: bool = False
    preferred_audio: AudioType = AudioType.SILENCE


class BedtimePlanRequest(BaseModel):
    telegram_id: int
    reminder_enabled: bool = False


class DayRecoveryRequest(BaseModel):
    telegram_id: int
    choice: str = Field(pattern="^(power_nap|meditation)$")
    free_minutes: int | None = Field(default=None, ge=5, le=60)
    reminder_enabled: bool = False


class TechniqueRequest(BaseModel):
    telegram_id: int
    kind: str = Field(pattern="^(quick_sleep|good_wake)$")
    quality: int | None = Field(default=None, ge=1, le=5)
    wake_feeling: int | None = Field(default=None, ge=1, le=5)


class RecommendationFeedbackRequest(BaseModel):
    telegram_id: int
    recommendation_id: UUID
    helpfulness: int = Field(ge=1, le=5)
    note: str | None = Field(default=None, max_length=1000)


class WakeCheckinRequest(BaseModel):
    telegram_id: int
    slept_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    feeling: int = Field(ge=1, le=5)
    helpfulness: int = Field(ge=1, le=5)
    audio: AudioType = AudioType.SILENCE
    note: str | None = Field(default=None, max_length=1000)


class CheckoutRequest(BaseModel):
    telegram_id: int
    plan_code: str
    idempotency_key: str


class CreateAlarmRequest(BaseModel):
    telegram_id: int
    minutes: int = Field(ge=1, le=1440)
    idempotency_key: str
