from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoricalSignal(BaseModel):
    mode: str
    duration_minutes: int = Field(ge=0, le=1440)
    subjective_sleep_quality_1_5: int | None = Field(default=None, ge=1, le=5)
    felt_after_waking_1_5: int | None = Field(default=None, ge=1, le=5)
    helpfulness_1_5: int | None = Field(default=None, ge=1, le=5)
    created_at: datetime


class RecommendationRequest(BaseModel):
    request_type: Literal["night", "day", "power_nap"]
    slept_last_night_minutes: int = Field(ge=0, le=1440)
    subjective_sleep_quality: int | None = Field(default=None, ge=1, le=5)
    current_energy: int | None = Field(default=None, ge=1, le=5)
    current_sleepiness: int | None = Field(default=None, ge=1, le=5)
    current_stress: int | None = Field(default=None, ge=1, le=5)
    free_time_minutes: int = Field(ge=0, le=720)
    desired_mode: str | None = None
    history: list[HistoricalSignal] = Field(default_factory=list)
    preferred_audio: str | None = None
    mode_preference: str | None = None
    dislikes_white_noise: bool = False
    likes_rain: bool = False
    likes_forest: bool = False
    likes_silence: bool = True

    @field_validator("preferred_audio")
    @classmethod
    def normalize_audio(cls, value: str | None) -> str | None:
        return value.lower() if value else None


class RecommendationOutput(BaseModel):
    recommended_mode: str
    recommended_duration_minutes: int | None
    recommended_steps: list[str]
    explanation_for_user: str
    optional_audio_type: str | None
    suggest_alarm: bool
    confidence_label: str
    followup_hint: str


class SessionRequestCreate(BaseModel):
    requested_mode: str
    free_time_minutes: int | None = None
    slept_last_night_minutes: int | None = None
    current_energy_1_5: int | None = Field(default=None, ge=1, le=5)
    current_sleepiness_1_5: int | None = Field(default=None, ge=1, le=5)
    current_stress_1_5: int | None = Field(default=None, ge=1, le=5)
    wants_alarm: bool = False
    recommendation_snapshot_json: dict = Field(default_factory=dict)


class SleepEntryCreate(BaseModel):
    mode: str
    duration_minutes: int = Field(ge=0, le=1440)
    subjective_sleep_quality_1_5: int | None = Field(default=None, ge=1, le=5)
    felt_after_waking_1_5: int | None = Field(default=None, ge=1, le=5)
    stress_before_sleep_1_5: int | None = Field(default=None, ge=1, le=5)
    sleepiness_before_sleep_1_5: int | None = Field(default=None, ge=1, le=5)
    helpfulness_1_5: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class StatsSummary(BaseModel):
    average_duration_minutes_last_7_days: float | None = None
    average_duration_minutes_last_30_days: float | None = None
    average_sleep_quality_last_30_days: float | None = None
    average_felt_after_last_30_days: float | None = None
    most_used_modes: list[str] = Field(default_factory=list)
    most_helpful_modes: list[str] = Field(default_factory=list)
    pattern_insights: list[str] = Field(default_factory=list)
    entries_count_last_30_days: int = 0


class AlarmCreateResult(BaseModel):
    alarm_id: int
    alarm_time: datetime
    code: str


class AlarmStopResult(BaseModel):
    stopped: bool
    reason: str
    alarm_id: int | None = None


class EventRecord(BaseModel):
    event_name: str
    user_id: int | None = None
    details: dict = Field(default_factory=dict)
