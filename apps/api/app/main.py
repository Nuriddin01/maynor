from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse

from apps.api.app.auth import require_admin
from apps.api.app.schemas import (
    BedtimePlanRequest,
    CheckoutRequest,
    CreateAlarmRequest,
    DayRecoveryRequest,
    ProfileRequest,
    RecommendationFeedbackRequest,
    RecommendationRequest,
    StartUserRequest,
    TechniqueRequest,
    WakeCheckinRequest,
)
from packages.billing.plans import PLANS
from packages.core.config import get_settings
from packages.core.logging import configure_logging
from packages.domain.models import AnalyticsEventName
from packages.services.facade import services


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Sleep Support Bot API", version="1.1.0")

    @app.get("/")
    async def index() -> dict[str, object]:
        return {
            "service": "Sleep Support Bot",
            "status": "running",
            "docs": "/docs",
            "health": "/health",
            "local_database": settings.local_db_path,
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readiness")
    async def readiness() -> dict[str, object]:
        return {"status": "ready", "env": settings.app_env}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        summary = services.analytics.summary(days=30)
        return "\n".join(
            [
                "# HELP sleep_support_events_total Product analytics events basis",
                "# TYPE sleep_support_events_total counter",
                f"sleep_support_events_total {summary['events']}",
                "# HELP sleep_support_active_users_basis Active users basis",
                "# TYPE sleep_support_active_users_basis gauge",
                f"sleep_support_active_users_basis {summary['active_users_basis']}",
            ]
        )

    @app.post("/users/start")
    async def start_user(payload: StartUserRequest) -> dict[str, object]:
        user = services.start_user(payload.telegram_id, payload.username)
        return {"id": str(user.id), "telegram_id": user.telegram_id, "created_at": user.created_at.isoformat()}

    @app.put("/users/{telegram_id}/profile")
    async def update_profile(telegram_id: int, payload: ProfileRequest) -> dict[str, object]:
        user = services.store.upsert_user(telegram_id)
        try:
            updated = services.update_profile(
                user,
                wake_time=payload.wake_time,
                timezone_name=payload.timezone,
                target_sleep_minutes=payload.target_sleep_minutes,
                default_nap_duration=payload.default_nap_duration,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return jsonable_encoder(updated)

    @app.post("/users/{telegram_id}/consents/accept-required")
    async def accept_consents(telegram_id: int) -> dict[str, str]:
        user = services.store.upsert_user(telegram_id)
        services.accept_consents(user.id)
        return {"status": "accepted"}

    @app.get("/users/{telegram_id}/history")
    async def user_history(telegram_id: int, limit: int = 20) -> dict[str, object]:
        user = services.store.upsert_user(telegram_id)
        return jsonable_encoder(services.history(user.id, limit))

    @app.post("/recommendations/night")
    async def recommendation(payload: RecommendationRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        if not services.consent.can_use_core_product(tuple(services.store.consents.get(user.id, []))):
            raise HTTPException(status_code=403, detail="required consent is missing")
        result = services.generate_night_recommendation(
            user=user,
            slept_minutes=payload.slept_last_night_minutes,
            quality=payload.quality,
            sleepiness=payload.sleepiness,
            stress=payload.stress,
            free_minutes=payload.free_minutes,
            needs_alarm=payload.needs_alarm,
            preferred_audio=payload.preferred_audio,
        )
        return jsonable_encoder(result)

    @app.post("/planning/bedtime")
    async def bedtime_plan(payload: BedtimePlanRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        result = services.generate_bedtime_plan(user, reminder_enabled=payload.reminder_enabled)
        return jsonable_encoder(result)

    @app.post("/recommendations/day-recovery")
    async def day_recovery(payload: DayRecoveryRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        try:
            result = services.generate_day_recovery(
                user,
                choice=payload.choice,
                free_minutes=payload.free_minutes,
                reminder_enabled=payload.reminder_enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return jsonable_encoder(result)

    @app.post("/recommendations/sleep-technique")
    async def sleep_technique(payload: TechniqueRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        try:
            result = services.generate_sleep_or_wake_technique(
                user,
                kind=payload.kind,
                quality=payload.quality,
                wake_feeling=payload.wake_feeling,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return jsonable_encoder(result)

    @app.post("/recommendations/feedback")
    async def recommendation_feedback(payload: RecommendationFeedbackRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        try:
            feedback = services.add_recommendation_feedback(
                user,
                recommendation_id=payload.recommendation_id,
                helpfulness=payload.helpfulness,
                note=payload.note,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return jsonable_encoder(feedback)

    @app.post("/checkins/wake")
    async def wake_checkin(payload: WakeCheckinRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        entry = services.add_wake_checkin(
            user=user,
            slept_minutes=payload.slept_minutes,
            quality=payload.quality,
            feeling=payload.feeling,
            helpfulness=payload.helpfulness,
            audio=payload.audio,
            note=payload.note,
        )
        return jsonable_encoder(entry)

    @app.get("/users/{telegram_id}/stats/{days}")
    async def user_stats(telegram_id: int, days: int) -> dict[str, object]:
        user = services.store.upsert_user(telegram_id)
        if days not in {7, 30}:
            raise HTTPException(status_code=400, detail="days must be 7 or 30")
        return jsonable_encoder(services.summary(user.id, days))

    @app.post("/alarms")
    async def create_alarm(payload: CreateAlarmRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        alarm = services.create_power_nap_alarm(user, payload.minutes, payload.idempotency_key)
        return jsonable_encoder(alarm)

    @app.post("/billing/checkout")
    async def checkout(payload: CheckoutRequest) -> dict[str, object]:
        user = services.store.upsert_user(payload.telegram_id)
        services.analytics.track(AnalyticsEventName.PREMIUM_SCREEN_VIEWED, user.id, {"plan": payload.plan_code})
        intent = services.billing.create_checkout(user.id, payload.plan_code, payload.idempotency_key)
        return jsonable_encoder(intent)

    @app.post("/billing/mock/confirm/{idempotency_key}")
    async def confirm_mock_payment(idempotency_key: str) -> dict[str, object]:
        subscription = services.billing.confirm_mock_payment(idempotency_key)
        services.analytics.track(AnalyticsEventName.SUBSCRIPTION_STARTED, subscription.user_id, {"plan": subscription.plan_code})
        return jsonable_encoder(subscription)

    @app.get("/admin/users", dependencies=[Depends(require_admin)])
    async def admin_users() -> list[dict[str, object]]:
        return [
            {"id": str(user.id), "telegram_id": user.telegram_id, "username": user.username, "created_at": user.created_at.isoformat()}
            for user in services.store.users_by_id.values()
        ]

    @app.get("/admin/analytics/summary", dependencies=[Depends(require_admin)])
    async def admin_analytics(days: int = 30) -> dict[str, object]:
        return services.analytics.summary(days)

    @app.get("/admin/content", dependencies=[Depends(require_admin)])
    async def admin_content() -> list[dict[str, object]]:
        return jsonable_encoder(services.content.all())

    @app.get("/admin/recommendation-rules", dependencies=[Depends(require_admin)])
    async def admin_rules() -> dict[str, object]:
        return {
            "rules": [
                "calculate_bedtime -> sleep debt + wake time + target sleep",
                "day recovery -> power nap or meditation based on free window and sleep debt",
                "quick_sleep -> breathing/body scan/cognitive shuffle based on sleep quality",
                "good_wake -> gentle/energizing wake based on sleep quality and wake-time light cycle",
                "high stress -> stress_down_protocol",
                "day window <10 -> recovery_break",
                "day window 10-20 -> power nap candidate",
                "poor noise feedback -> silence fallback",
                "short-flow helpfulness bias -> shorter protocols",
            ]
        }

    @app.get("/admin/feature-flags", dependencies=[Depends(require_admin)])
    async def feature_flags() -> dict[str, object]:
        return {"flags": {"premium_weekly_insights": True, "llm_summaries": False, "wearables": False}}

    @app.get("/admin/consent-versions", dependencies=[Depends(require_admin)])
    async def consent_versions() -> list[dict[str, object]]:
        return jsonable_encoder(services.consent.active_versions())

    @app.get("/admin/subscriptions/plans", dependencies=[Depends(require_admin)])
    async def plans() -> dict[str, object]:
        return jsonable_encoder(PLANS)

    @app.get("/admin/alarms", dependencies=[Depends(require_admin)])
    async def admin_alarms() -> list[dict[str, object]]:
        store = services.alarms._store
        items = getattr(store, "_items", {})
        return jsonable_encoder(list(items.values()))

    @app.get("/admin/users/{user_id}/export", dependencies=[Depends(require_admin)])
    async def export_user(user_id: UUID) -> dict[str, object]:
        if user_id not in services.store.users_by_id:
            raise HTTPException(status_code=404, detail="user not found")
        return jsonable_encoder(services.store.export_user(user_id))

    @app.delete("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
    async def delete_user(user_id: UUID) -> dict[str, str]:
        if user_id not in services.store.users_by_id:
            raise HTTPException(status_code=404, detail="user not found")
        services.store.delete_user(user_id)
        return {"status": "deleted"}

    @app.get("/admin/audit-logs", dependencies=[Depends(require_admin)])
    async def audit_logs() -> list[dict[str, object]]:
        return services.store.audit_logs

    @app.get("/admin/time", dependencies=[Depends(require_admin)])
    async def admin_time() -> dict[str, str]:
        return {"utc": datetime.now(timezone.utc).isoformat()}

    return app


app = create_app()
