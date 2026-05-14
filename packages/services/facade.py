from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from typing import Any
import sys
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from packages.analytics.events import AnalyticsService
from packages.billing.providers import MockBillingProvider
from packages.billing.service import BillingService
from packages.content.registry import ContentRegistry, default_registry
from packages.core.config import get_settings
from packages.domain.alarms import AlarmService, InMemoryAlarmStore
from packages.domain.consent import ConsentService, ConsentVersion
from packages.domain.models import (
    Alarm,
    AnalyticsEventName,
    AudioType,
    ConsentType,
    DecisionTraceItem,
    Recommendation,
    RecommendationFeedback,
    RecommendationMode,
    SleepEntry,
    SleepMode,
    SleepRequest,
    UserPreferences,
    WakeIntensity,
    new_uuid,
)
from packages.domain.recommendation_engine import RecommendationContext, RecommendationEngine
from packages.domain.stats import SleepSummary, StatsService
from packages.services.memory import InMemoryAppStore, UserRecord
from packages.services.sqlite_store import SQLiteAlarmStore, SQLiteAnalyticsStore, SQLiteAppStore, SQLiteBillingStore

DISCLAIMER = "Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, обратитесь к специалисту."


def default_consent_versions() -> tuple[ConsentVersion, ...]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (
        ConsentVersion(ConsentType.CORE, "2026-01", True, "core-v1", now),
        ConsentVersion(ConsentType.PRIVACY, "2026-01", True, "privacy-v1", now),
        ConsentVersion(ConsentType.MARKETING, "2026-01", False, "marketing-v1", now),
    )


@dataclass
class AppServices:
    store: Any
    recommendation_engine: RecommendationEngine
    stats_service: StatsService
    analytics: AnalyticsService
    billing: BillingService
    alarms: AlarmService
    consent: ConsentService
    content: ContentRegistry

    @classmethod
    def in_memory(cls) -> AppServices:
        return cls(
            store=InMemoryAppStore(),
            recommendation_engine=RecommendationEngine(),
            stats_service=StatsService(),
            analytics=AnalyticsService(),
            billing=BillingService(MockBillingProvider()),
            alarms=AlarmService(InMemoryAlarmStore()),
            consent=ConsentService(default_consent_versions()),
            content=default_registry(),
        )

    @classmethod
    def local(cls, db_path: str | None = None) -> AppServices:
        settings = get_settings()
        path = db_path or settings.local_db_path
        return cls(
            store=SQLiteAppStore(path),
            recommendation_engine=RecommendationEngine(),
            stats_service=StatsService(),
            analytics=AnalyticsService(SQLiteAnalyticsStore(path)),
            billing=BillingService(MockBillingProvider(), SQLiteBillingStore(path)),
            alarms=AlarmService(SQLiteAlarmStore(path)),
            consent=ConsentService(default_consent_versions()),
            content=default_registry(),
        )

    def start_user(self, telegram_id: int, username: str | None) -> UserRecord:
        user = self.store.upsert_user(telegram_id, username)
        self.analytics.track(AnalyticsEventName.STARTED_FLOW, user.id, {"source": "start"})
        return user

    def accept_consents(self, user_id: UUID) -> None:
        self.store.accept_required_consents(user_id, self.consent.active_versions())

    def update_profile(
        self,
        user: UserRecord,
        wake_time: time | None = None,
        timezone_name: str | None = None,
        target_sleep_minutes: int | None = None,
        default_nap_duration: int | None = None,
    ) -> UserRecord:
        preferences = user.preferences
        if target_sleep_minutes is not None and not 300 <= target_sleep_minutes <= 660:
            raise ValueError("target_sleep_minutes must be between 300 and 660")
        if default_nap_duration is not None and default_nap_duration not in {10, 15, 20}:
            raise ValueError("default_nap_duration must be 10, 15 or 20")
        preferences = replace(
            preferences,
            wake_time=wake_time if wake_time is not None else preferences.wake_time,
            timezone=timezone_name or preferences.timezone,
            target_sleep_minutes=target_sleep_minutes or preferences.target_sleep_minutes,
            default_nap_duration=default_nap_duration or preferences.default_nap_duration,
        )
        return self.store.update_preferences(user.id, preferences)

    def generate_night_recommendation(
        self,
        user: UserRecord,
        slept_minutes: int,
        quality: int,
        sleepiness: int,
        stress: int,
        free_minutes: int,
        needs_alarm: bool,
        preferred_audio: AudioType,
    ) -> Recommendation:
        request = SleepRequest(
            user_id=user.id,
            mode=SleepMode.NIGHT_SLEEP,
            slept_last_night_minutes=slept_minutes,
            quality=quality,
            sleepiness=sleepiness,
            stress=stress,
            free_minutes=free_minutes,
            needs_alarm=needs_alarm,
            preferred_audio=preferred_audio,
            created_at=datetime.now(timezone.utc),
            timezone=user.preferences.timezone,
        )
        recommendation = self.recommendation_engine.generate(
            RecommendationContext(
                request=request,
                preferences=user.preferences,
                history_7d=tuple(self.store.entries.get(user.id, [])[-7:]),
                history_30d=tuple(self.store.entries.get(user.id, [])[-30:]),
                is_premium=self.billing.has_feature(user.id, "advanced_flows"),
            )
        )
        self.store.add_recommendation(recommendation)
        self.analytics.track(
            AnalyticsEventName.RECOMMENDATION_GENERATED,
            user.id,
            {"mode": recommendation.recommended_mode.value, "duration": recommendation.duration_minutes},
        )
        return recommendation

    def generate_bedtime_plan(self, user: UserRecord, reminder_enabled: bool) -> Recommendation:
        entries = self._night_entries(user.id, 7)
        target = user.preferences.target_sleep_minutes
        has_profile_data = user.preferences.wake_time is not None and bool(entries)
        sleep_debt = self._sleep_debt(entries, target) if entries else 0
        extra_recovery = min(90, sleep_debt // 3) if has_profile_data else 0
        sleep_today = min(600, target + extra_recovery)
        wake_time = user.preferences.wake_time or time(hour=7, minute=30)
        bedtime = self._minus_minutes(wake_time, sleep_today)
        mode = RecommendationMode.SLEEP_DEBT_RECOVERY_PLAN if sleep_debt > 0 else RecommendationMode.BEDTIME_PLAN
        trace = [
            DecisionTraceItem("target_sleep", f"ориентир сна на сегодня: {target} минут", 2),
            DecisionTraceItem("sleep_debt", f"долг сна: {sleep_debt} минут", 3),
        ]
        if not has_profile_data:
            trace.append(DecisionTraceItem("baseline_fallback", "нет времени подъема или записей сна, использована базовая настройка", 4))
        steps = self._bedtime_steps(bedtime, wake_time, sleep_debt, has_profile_data)
        recommendation = Recommendation(
            id=new_uuid(),
            user_id=user.id,
            request_mode=SleepMode.BEDTIME_PLANNING,
            recommended_mode=mode,
            duration_minutes=sleep_today,
            steps=steps,
            audio=AudioType.NO_AUDIO,
            follow_up_minutes=30,
            should_create_alarm=reminder_enabled,
            decision_trace=tuple(trace),
            disclaimer=DISCLAIMER,
            created_at=datetime.now(timezone.utc),
            snapshot={
                "scenario": "calculate_bedtime",
                "sleep_debt_minutes": sleep_debt,
                "recommended_bedtime": bedtime.strftime("%H:%M"),
                "target_wake_time": wake_time.strftime("%H:%M"),
                "optimal_sleep_minutes_today": sleep_today,
                "baseline_used": not has_profile_data,
                "reminder_offer": True,
                "plain_text": self._bedtime_plain_text(bedtime, wake_time, sleep_today, sleep_debt, has_profile_data),
            },
        )
        self.store.add_recommendation(recommendation)
        self.analytics.track(
            AnalyticsEventName.RECOMMENDATION_GENERATED,
            user.id,
            {"mode": recommendation.recommended_mode.value, "sleep_debt_minutes": sleep_debt},
        )
        return recommendation

    def generate_day_recovery(
        self,
        user: UserRecord,
        choice: str,
        free_minutes: int | None,
        reminder_enabled: bool,
    ) -> Recommendation:
        if choice not in {"power_nap", "meditation"}:
            raise ValueError("choice must be power_nap or meditation")
        entries = self._night_entries(user.id, 7)
        target = user.preferences.target_sleep_minutes
        sleep_debt = self._sleep_debt(entries, target) if entries else 0
        has_profile_data = user.preferences.wake_time is not None and bool(entries)
        if free_minutes is None:
            free_minutes = self._recommended_day_window(choice, sleep_debt, has_profile_data, user.preferences.default_nap_duration)
        free_minutes = max(5, min(60, free_minutes))
        if choice == "power_nap":
            duration = self._power_nap_duration(free_minutes, user.preferences.default_nap_duration)
            mode = {
                10: RecommendationMode.POWER_NAP_10,
                15: RecommendationMode.POWER_NAP_15,
                20: RecommendationMode.POWER_NAP_20,
            }[duration]
            request_mode = SleepMode.POWER_NAP
            steps = (
                f"Поставь таймер на {duration} минут и убери уведомления.",
                "Первые 1-2 минуты просто спокойно выдыхай, не заставляя себя уснуть.",
                "После сигнала сядь, сделай несколько вдохов и выпей воды.",
            )
            audio = AudioType.SILENCE
        else:
            duration = 5 if free_minutes < 8 else 10 if free_minutes < 14 else 15
            mode = {
                5: RecommendationMode.MEDITATION_5,
                10: RecommendationMode.MEDITATION_10,
                15: RecommendationMode.MEDITATION_15,
            }[duration]
            request_mode = SleepMode.MEDITATION
            steps = (
                f"Выдели {duration} минут без переписок и задач.",
                "Сядь удобно. На вдохе замечай напряжение, на выдохе отпускай плечи и челюсть.",
                "Если отвлекся, спокойно возвращайся к дыханию. Это нормально.",
            )
            audio = AudioType.BREATHING_ONLY
        trace = [DecisionTraceItem("choice", f"выбран сценарий {choice}", 2)]
        if has_profile_data:
            trace.append(DecisionTraceItem("history_based_debt", f"расчет долга сна по истории: {sleep_debt} минут", 3))
        else:
            trace.append(DecisionTraceItem("needs_free_time_input", "истории сна мало, нужен ввод свободного окна", 4))
        recommendation = Recommendation(
            id=new_uuid(),
            user_id=user.id,
            request_mode=request_mode,
            recommended_mode=mode,
            duration_minutes=duration,
            steps=steps,
            audio=audio,
            follow_up_minutes=5,
            should_create_alarm=reminder_enabled,
            decision_trace=tuple(trace),
            disclaimer=DISCLAIMER,
            created_at=datetime.now(timezone.utc),
            snapshot={
                "scenario": choice,
                "sleep_debt_minutes": sleep_debt,
                "has_profile_data": has_profile_data,
                "free_minutes_used": free_minutes,
                "reminder_offer": True,
                "needs_free_time_input": not has_profile_data,
            },
        )
        self.store.add_recommendation(recommendation)
        self.analytics.track(
            AnalyticsEventName.RECOMMENDATION_GENERATED,
            user.id,
            {"mode": recommendation.recommended_mode.value, "sleep_debt_minutes": sleep_debt},
        )
        return recommendation

    def generate_sleep_or_wake_technique(
        self,
        user: UserRecord,
        kind: str,
        quality: int | None,
        wake_feeling: int | None,
    ) -> Recommendation:
        if kind not in {"quick_sleep", "good_wake"}:
            raise ValueError("kind must be quick_sleep or good_wake")
        entries = self._night_entries(user.id, 7)
        latest = entries[-1] if entries else None
        has_profile_data = user.preferences.wake_time is not None and latest is not None
        inferred_quality = latest.quality if latest else quality or 3
        inferred_feeling = latest.post_wake_feeling if latest else wake_feeling or 3
        sleep_minutes = latest.duration_minutes if latest else user.preferences.target_sleep_minutes
        wake_hour = user.preferences.wake_time.hour if user.preferences.wake_time else 7
        light_cycle = self._light_cycle_bucket(wake_hour)
        if kind == "quick_sleep":
            request_mode = SleepMode.QUICK_SLEEP_TECHNIQUE
            if inferred_quality <= 2 or sleep_minutes < 360:
                mode = RecommendationMode.QUICK_SLEEP_BODY_SCAN
                steps = (
                    "Не пытайся срочно уснуть. Сначала снижаем напряжение.",
                    "Медленно пройди вниманием по телу: лоб, челюсть, плечи, грудь, живот, ноги.",
                    "На каждом выдохе отпускай одну маленькую зону напряжения.",
                )
            elif inferred_feeling <= 2:
                mode = RecommendationMode.QUICK_SLEEP_COGNITIVE_SHUFFLE
                steps = (
                    "Выбери нейтральное слово, например сон.",
                    "На каждую букву вспоминай простые предметы: с - стол, о - окно, н - носок.",
                    "Не ищи идеальные варианты. Задача - мягко разгрузить внимание.",
                )
            else:
                mode = RecommendationMode.QUICK_SLEEP_BREATHING
                steps = (
                    "Ляг удобно и сделай выдох длиннее вдоха.",
                    "Повтори 8-10 циклов: вдох спокойно, выдох чуть медленнее.",
                    "Если мысли возвращаются, отмечай их и снова переходи к выдоху.",
                )
        else:
            request_mode = SleepMode.GOOD_WAKE_TECHNIQUE
            if inferred_quality <= 2 or sleep_minutes < 360 or light_cycle == "early_dark_or_very_early":
                mode = RecommendationMode.GOOD_WAKE_GENTLE
                steps = (
                    "Не вскакивай резко. Сначала сядь и дай глазам привыкнуть к свету.",
                    "Сделай 5 спокойных вдохов, затем мягко разомни шею и плечи.",
                    "Выпей воды и только после этого открывай сообщения.",
                )
            else:
                mode = RecommendationMode.GOOD_WAKE_ENERGIZE
                steps = (
                    "Сядь сразу после сигнала и включи свет или подойди к окну.",
                    "Сделай 30-60 секунд простой разминки: плечи, руки, стопы.",
                    "Назови один маленький первый шаг дня и начни с него.",
                )
        trace = [
            DecisionTraceItem("quality", f"качество сна: {inferred_quality}", 2),
            DecisionTraceItem("sleep_amount", f"сон: {sleep_minutes} минут", 2),
            DecisionTraceItem("light_cycle", f"оценка времени подъема: {light_cycle}", 1),
        ]
        if not has_profile_data:
            trace.append(DecisionTraceItem("fallback_questions", "нет полной истории, использована самооценка пользователя", 4))
        recommendation = Recommendation(
            id=new_uuid(),
            user_id=user.id,
            request_mode=request_mode,
            recommended_mode=mode,
            duration_minutes=5 if kind == "good_wake" else 8,
            steps=steps,
            audio=AudioType.NO_AUDIO,
            follow_up_minutes=None,
            should_create_alarm=False,
            decision_trace=tuple(trace),
            disclaimer=DISCLAIMER,
            created_at=datetime.now(timezone.utc),
            snapshot={
                "scenario": kind,
                "has_profile_data": has_profile_data,
                "quality_used": inferred_quality,
                "wake_feeling_used": inferred_feeling,
                "sleep_minutes_used": sleep_minutes,
                "light_cycle": light_cycle,
                "feedback_prompt": "Оцени полезность рекомендации от 1 до 5 после выполнения.",
            },
        )
        self.store.add_recommendation(recommendation)
        self.analytics.track(
            AnalyticsEventName.RECOMMENDATION_GENERATED,
            user.id,
            {"mode": recommendation.recommended_mode.value, "kind": kind},
        )
        return recommendation

    def add_recommendation_feedback(self, user: UserRecord, recommendation_id: UUID, helpfulness: int, note: str | None) -> RecommendationFeedback:
        if helpfulness < 1 or helpfulness > 5:
            raise ValueError("helpfulness must be between 1 and 5")
        known = {item.id for item in self.store.recommendations.get(user.id, [])}
        if recommendation_id not in known:
            raise KeyError("recommendation not found for user")
        feedback = RecommendationFeedback(
            recommendation_id=recommendation_id,
            user_id=user.id,
            helpfulness=helpfulness,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
        self.store.add_recommendation_feedback(feedback)
        self.analytics.track(AnalyticsEventName.RECOMMENDATION_FOLLOWED, user.id, {"helpfulness": helpfulness})
        return feedback

    def create_power_nap_alarm(self, user: UserRecord, minutes: int, idempotency_key: str) -> Alarm:
        alarm = self.alarms.create_relative(
            user_id=user.id,
            minutes=minutes,
            timezone_name=user.preferences.timezone,
            wake_intensity=WakeIntensity.NORMAL,
            now=datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
        )
        self.analytics.track(AnalyticsEventName.ALARM_CREATED, user.id, {"minutes": minutes})
        return alarm

    def add_wake_checkin(
        self,
        user: UserRecord,
        slept_minutes: int,
        quality: int,
        feeling: int,
        helpfulness: int,
        audio: AudioType,
        note: str | None,
    ) -> SleepEntry:
        entry = SleepEntry(
            user_id=user.id,
            mode=SleepMode.NIGHT_SLEEP,
            duration_minutes=slept_minutes,
            quality=quality,
            post_wake_feeling=feeling,
            helpfulness=helpfulness,
            audio_used=audio,
            created_at=datetime.now(timezone.utc),
            note=note,
        )
        self.store.add_entry(entry)
        self.analytics.track(AnalyticsEventName.WAKE_CHECKIN_COMPLETED, user.id, {"quality": quality, "helpfulness": helpfulness})
        return entry

    def summary(self, user_id: UUID, days: int) -> SleepSummary:
        return self.stats_service.summarize(tuple(self.store.entries.get(user_id, [])), datetime.now(timezone.utc), days)

    def history(self, user_id: UUID, limit: int = 20) -> dict[str, object]:
        entries = list(self.store.entries.get(user_id, []))[-limit:]
        recommendations = list(self.store.recommendations.get(user_id, []))[-limit:]
        return {
            "sleep_entries": entries,
            "recommendations": recommendations,
            "recommendation_feedback": list(self.store.recommendation_feedback.get(user_id, []))[-limit:],
        }

    def _night_entries(self, user_id: UUID, limit: int) -> list[SleepEntry]:
        entries = [entry for entry in self.store.entries.get(user_id, []) if entry.mode == SleepMode.NIGHT_SLEEP]
        return entries[-limit:]

    def _sleep_debt(self, entries: list[SleepEntry], target: int) -> int:
        return sum(max(0, target - entry.duration_minutes) for entry in entries)

    def _minus_minutes(self, base: time, minutes: int) -> time:
        dt = datetime(2026, 1, 2, base.hour, base.minute, tzinfo=timezone.utc) - timedelta(minutes=minutes)
        return dt.time().replace(second=0, microsecond=0)

    def _bedtime_steps(self, bedtime: time, wake_time: time, sleep_debt: int, has_profile_data: bool) -> tuple[str, ...]:
        intro = (
            f"Сегодня ориентир отбоя - {bedtime.strftime('%H:%M')}, подъем - {wake_time.strftime('%H:%M')}."
            if has_profile_data
            else f"Данных пока мало, поэтому беру базовый ориентир: отбой около {bedtime.strftime('%H:%M')}, подъем около {wake_time.strftime('%H:%M')}."
        )
        debt_text = "Долг сна сейчас не выглядит выраженным." if sleep_debt == 0 else f"Оценочный долг сна: {sleep_debt} минут. Не закрывай его резко за одну ночь."
        return (
            intro,
            debt_text,
            "За 30 минут до отбоя снизь яркость экрана и убери активные переписки.",
            "Если хочешь, включи напоминание - бот заранее напишет, что пора готовиться ко сну.",
        )

    def _bedtime_plain_text(self, bedtime: time, wake_time: time, sleep_today: int, sleep_debt: int, has_profile_data: bool) -> str:
        basis = "по твоей истории сна" if has_profile_data else "по базовой норме, потому что данных пока мало"
        return (
            f"Расчет {basis}: сегодня лучше лечь около {bedtime.strftime('%H:%M')} и целиться примерно в "
            f"{sleep_today // 60} ч {sleep_today % 60:02d} мин сна до подъема в {wake_time.strftime('%H:%M')}. "
            f"Оценочный долг сна: {sleep_debt} мин."
        )

    def _recommended_day_window(self, choice: str, sleep_debt: int, has_profile_data: bool, default_nap_duration: int) -> int:
        if choice == "meditation":
            return 10 if not has_profile_data or sleep_debt < 90 else 15
        if not has_profile_data:
            return default_nap_duration
        if sleep_debt >= 180:
            return 20
        if sleep_debt >= 60:
            return 15
        return 10

    def _power_nap_duration(self, free_minutes: int, default_duration: int) -> int:
        if free_minutes < 13:
            return 10
        if free_minutes < 18:
            return 15
        if default_duration in {10, 15, 20} and default_duration <= free_minutes:
            return default_duration
        return 20

    def _light_cycle_bucket(self, wake_hour: int) -> str:
        if wake_hour < 6:
            return "early_dark_or_very_early"
        if wake_hour < 10:
            return "morning"
        if wake_hour < 13:
            return "late_morning"
        return "daytime_or_irregular"

    def _safe_zone(self, timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")


def default_services() -> AppServices:
    if "pytest" in sys.modules:
        return AppServices.in_memory()
    return AppServices.local()


services = default_services()
