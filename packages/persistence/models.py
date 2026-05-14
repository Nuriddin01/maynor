from __future__ import annotations

from datetime import datetime

HAS_SQLALCHEMY = True

try:
    from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
    from sqlalchemy.dialects.postgresql import JSONB, UUID
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
except ImportError:
    HAS_SQLALCHEMY = False
    BigInteger = Boolean = DateTime = ForeignKey = Integer = String = Text = UniqueConstraint = text = None
    JSONB = UUID = None
    DeclarativeBase = object
    Mapped = object

    def mapped_column(*args: object, **kwargs: object) -> object:
        return None

    def relationship(*args: object, **kwargs: object) -> object:
        return None


if HAS_SQLALCHEMY:
    class Base(DeclarativeBase):
        pass


    class User(Base):
        __tablename__ = "users"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
        username: Mapped[str | None] = mapped_column(String(255))
        status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class UserProfile(Base):
        __tablename__ = "user_profiles"

        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
        display_name: Mapped[str | None] = mapped_column(String(255))
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class UserPreferences(Base):
        __tablename__ = "user_preferences"

        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
        timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
        language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
        audio_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
        disliked_audio: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
        default_nap_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
        dnd_window: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
        analytics_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


    class UserConsent(Base):
        __tablename__ = "user_consents"
        __table_args__ = (UniqueConstraint("user_id", "consent_type", "version", name="uq_user_consent_version"),)

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
        version: Mapped[str] = mapped_column(String(32), nullable=False)
        accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
        accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


    class SleepEntry(Base):
        __tablename__ = "sleep_entries"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        mode: Mapped[str] = mapped_column(String(64), nullable=False)
        duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
        quality: Mapped[int] = mapped_column(Integer, nullable=False)
        post_wake_feeling: Mapped[int] = mapped_column(Integer, nullable=False)
        helpfulness: Mapped[int] = mapped_column(Integer, nullable=False)
        audio_used: Mapped[str] = mapped_column(String(64), nullable=False)
        note: Mapped[str | None] = mapped_column(Text)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


    class SessionRequest(Base):
        __tablename__ = "session_requests"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        mode: Mapped[str] = mapped_column(String(64), nullable=False)
        payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class Recommendation(Base):
        __tablename__ = "recommendations"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        session_request_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey("session_requests.id", ondelete="SET NULL"))
        request_mode: Mapped[str] = mapped_column(String(64), nullable=False)
        recommended_mode: Mapped[str] = mapped_column(String(64), nullable=False)
        duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
        audio: Mapped[str] = mapped_column(String(64), nullable=False)
        snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


    class RecommendationFeedback(Base):
        __tablename__ = "recommendation_feedback"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        recommendation_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
        helpfulness: Mapped[int] = mapped_column(Integer, nullable=False)
        note: Mapped[str | None] = mapped_column(Text)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class Alarm(Base):
        __tablename__ = "alarms"
        __table_args__ = (UniqueConstraint("idempotency_key", name="uq_alarm_idempotency"),)

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
        timezone: Mapped[str] = mapped_column(String(64), nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
        wake_intensity: Mapped[str] = mapped_column(String(32), nullable=False)
        dismiss_code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
        max_repeats: Mapped[int] = mapped_column(Integer, nullable=False)
        repeats_done: Mapped[int] = mapped_column(Integer, nullable=False)
        idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class AlarmEvent(Base):
        __tablename__ = "alarm_events"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        alarm_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("alarms.id", ondelete="CASCADE"), nullable=False, index=True)
        event_type: Mapped[str] = mapped_column(String(64), nullable=False)
        payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class Subscription(Base):
        __tablename__ = "subscriptions"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
        provider: Mapped[str] = mapped_column(String(64), nullable=False)
        current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
        canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


    class Payment(Base):
        __tablename__ = "payments"
        __table_args__ = (UniqueConstraint("provider", "idempotency_key", name="uq_payment_provider_idempotency"),)

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        subscription_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"))
        provider: Mapped[str] = mapped_column(String(64), nullable=False)
        amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
        currency: Mapped[str] = mapped_column(String(8), nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
        idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
        payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class PremiumEntitlement(Base):
        __tablename__ = "premium_entitlements"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
        feature: Mapped[str] = mapped_column(String(64), nullable=False)
        valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class AnalyticsEvent(Base):
        __tablename__ = "analytics_events"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        user_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
        name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
        properties: Mapped[dict] = mapped_column(JSONB, nullable=False)
        occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


    class ContentItem(Base):
        __tablename__ = "content_items"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
        title: Mapped[str] = mapped_column(String(255), nullable=False)
        language: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
        type: Mapped[str] = mapped_column(String(64), nullable=False)
        body: Mapped[str] = mapped_column(Text, nullable=False)
        audio_type: Mapped[str] = mapped_column(String(64), nullable=False)
        premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class ContentTag(Base):
        __tablename__ = "content_tags"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        content_item_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
        tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


    class ExperimentFlag(Base):
        __tablename__ = "experiment_flags"

        key: Mapped[str] = mapped_column(String(128), primary_key=True)
        enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
        payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class AdminUser(Base):
        __tablename__ = "admin_users"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
        password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
        role: Mapped[str] = mapped_column(String(64), nullable=False)
        active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


    class AuditLog(Base):
        __tablename__ = "audit_logs"

        id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
        actor_admin_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"))
        action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
        entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
        entity_id: Mapped[str | None] = mapped_column(String(128))
        payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

else:
    class Base:
        metadata = None
