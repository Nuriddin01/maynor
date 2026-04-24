from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    preferred_language: Mapped[str] = mapped_column(String(10), default="ru")
    premium_status: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sleep_entries: Mapped[list["SleepEntry"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    session_requests: Mapped[list["SessionRequest"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class SleepEntry(Base):
    __tablename__ = "sleep_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, default=lambda: utcnow().date(), index=True)
    mode: Mapped[str] = mapped_column(String(80), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    subjective_sleep_quality_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    felt_after_waking_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_before_sleep_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleepiness_before_sleep_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    helpfulness_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="sleep_entries")


class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alarm_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    code: Mapped[str] = mapped_column(String(20))
    repeat_attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    stop_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="alarms")


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_preferences_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    preferred_audio: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dislikes_white_noise: Mapped[bool] = mapped_column(Boolean, default=False)
    likes_rain: Mapped[bool] = mapped_column(Boolean, default=False)
    likes_forest: Mapped[bool] = mapped_column(Boolean, default=False)
    likes_silence: Mapped[bool] = mapped_column(Boolean, default=True)
    default_nap_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_format: Mapped[str] = mapped_column(String(10), default="24h")
    enable_sleep_hygiene_tips: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_audio_recommendations: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="preferences")


class SessionRequest(Base):
    __tablename__ = "session_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    requested_mode: Mapped[str] = mapped_column(String(80), index=True)
    free_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slept_last_night_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_energy_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_sleepiness_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_stress_1_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wants_alarm: Mapped[bool] = mapped_column(Boolean, default=False)
    recommendation_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="session_requests")
