from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.domain.models import (
    AudioType,
    DecisionTraceItem,
    Recommendation,
    RecommendationMode,
    SleepEntry,
    SleepMode,
    SleepRequest,
    UserPreferences,
    new_uuid,
)
from packages.domain.validation import validate_sleep_numbers

DISCLAIMER = "Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, обратитесь к специалисту."


@dataclass(frozen=True)
class RecommendationContext:
    request: SleepRequest
    preferences: UserPreferences
    history_7d: tuple[SleepEntry, ...] = ()
    history_30d: tuple[SleepEntry, ...] = ()
    is_premium: bool = False


class RecommendationEngine:
    def generate(self, context: RecommendationContext) -> Recommendation:
        request = context.request
        validate_sleep_numbers(
            request.slept_last_night_minutes,
            request.quality,
            request.sleepiness,
            request.stress,
            request.free_minutes,
        )
        trace: list[DecisionTraceItem] = []
        mode, duration = self._select_mode(context, trace)
        audio = self._select_audio(context, trace)
        steps = self._build_steps(mode, request, context.is_premium)
        follow_up = self._follow_up_minutes(mode)
        snapshot = {
            "slept_last_night_minutes": request.slept_last_night_minutes,
            "quality": request.quality,
            "sleepiness": request.sleepiness,
            "stress": request.stress,
            "free_minutes": request.free_minutes,
            "audio": audio.value,
            "history_7d_count": len(context.history_7d),
            "history_30d_count": len(context.history_30d),
            "premium": context.is_premium,
            "trace": [item.__dict__ for item in trace],
        }
        return Recommendation(
            id=new_uuid(),
            user_id=request.user_id,
            request_mode=request.mode,
            recommended_mode=mode,
            duration_minutes=duration,
            steps=steps,
            audio=audio,
            follow_up_minutes=follow_up,
            should_create_alarm=request.needs_alarm,
            decision_trace=tuple(trace),
            disclaimer=DISCLAIMER,
            created_at=datetime.now(tz=request.created_at.tzinfo),
            snapshot=snapshot,
        )

    def _select_mode(
        self,
        context: RecommendationContext,
        trace: list[DecisionTraceItem],
    ) -> tuple[RecommendationMode, int]:
        request = context.request
        short_flow_bias = self._short_flow_bias(context.history_30d)
        if short_flow_bias:
            trace.append(DecisionTraceItem("short_flow_bias", "history shows better response to shorter flows", 2))

        if request.mode == SleepMode.POWER_NAP:
            duration = self._power_nap_duration(request.free_minutes, context.preferences.default_nap_duration)
            trace.append(DecisionTraceItem("power_nap_window", f"selected {duration} minutes for available window", 3))
            mode = {
                10: RecommendationMode.POWER_NAP_10,
                15: RecommendationMode.POWER_NAP_15,
                20: RecommendationMode.POWER_NAP_20,
            }[duration]
            return mode, duration

        if request.mode == SleepMode.DAY_REST:
            if request.free_minutes < 10:
                trace.append(DecisionTraceItem("short_day_window", "less than 10 minutes available", 3))
                return RecommendationMode.RECOVERY_BREAK, min(8, request.free_minutes)
            if request.free_minutes <= 20:
                trace.append(DecisionTraceItem("day_power_nap_candidate", "10-20 minutes available", 3))
                return RecommendationMode.POWER_NAP_15, min(15, request.free_minutes)
            if request.free_minutes <= 30:
                trace.append(DecisionTraceItem("guided_nap_window", "20-30 minutes available", 2))
                return RecommendationMode.GUIDED_NAP_ATTEMPT, min(25, request.free_minutes)
            trace.append(DecisionTraceItem("long_rest_caution", "more than 30 minutes available", 2))
            return RecommendationMode.LONG_REST_SESSION, min(35, request.free_minutes)

        if request.stress >= 4:
            trace.append(DecisionTraceItem("high_stress", "calming first because stress is high", 4))
            return RecommendationMode.STRESS_DOWN_PROTOCOL, min(max(12, request.free_minutes), 25)
        if request.slept_last_night_minutes < 300 and request.sleepiness >= 4:
            trace.append(DecisionTraceItem("low_sleep_high_sleepiness", "gentle protocol for significant sleep pressure", 3))
            return RecommendationMode.LOW_ENERGY_GENTLE_SLEEP, min(max(10, request.free_minutes), 20)
        if request.free_minutes <= 8 or short_flow_bias:
            trace.append(DecisionTraceItem("ultra_short_window", "short preparation window", 2))
            return RecommendationMode.ULTRA_SHORT_WIND_DOWN, min(request.free_minutes, 8)
        if request.free_minutes <= 15:
            trace.append(DecisionTraceItem("short_window", "short but enough for wind down", 2))
            return RecommendationMode.SHORT_WIND_DOWN, request.free_minutes
        if request.quality <= 2:
            trace.append(DecisionTraceItem("low_quality_sleep", "recent sleep quality is low", 2))
            return RecommendationMode.CALM_NIGHT_PROTOCOL, min(request.free_minutes, 25)
        if self._is_late_night(request.created_at):
            trace.append(DecisionTraceItem("late_night", "late local time favors quick shutdown", 2))
            return RecommendationMode.LATE_NIGHT_QUICK_SHUTDOWN, min(request.free_minutes, 15)
        trace.append(DecisionTraceItem("default_standard", "balanced night flow", 1))
        return RecommendationMode.STANDARD_WIND_DOWN, min(request.free_minutes, 30)

    def _select_audio(self, context: RecommendationContext, trace: list[DecisionTraceItem]) -> AudioType:
        request = context.request
        disliked = set(context.preferences.disliked_audio)
        if request.preferred_audio in disliked:
            trace.append(DecisionTraceItem("audio_disliked", f"{request.preferred_audio.value} was disliked before", 3))
            return AudioType.SILENCE
        if request.preferred_audio in {AudioType.WHITE_NOISE, AudioType.PINK_NOISE} and self._noise_performed_poorly(context.history_30d):
            trace.append(DecisionTraceItem("noise_poor_feedback", "noise formats had weak helpfulness", 2))
            return AudioType.SILENCE
        if request.preferred_audio == AudioType.GUIDED_TEXT:
            trace.append(DecisionTraceItem("guided_text_requested", "text guidance selected", 1))
            return AudioType.GUIDED_TEXT
        return request.preferred_audio

    def _build_steps(self, mode: RecommendationMode, request: SleepRequest, is_premium: bool) -> tuple[str, ...]:
        common_end = "Если сон не приходит, не дави на себя. Вернись к спокойному дыханию и убери ожидание результата."
        steps_by_mode: dict[RecommendationMode, tuple[str, ...]] = {
            RecommendationMode.ULTRA_SHORT_WIND_DOWN: (
                "Убери яркий экран и поставь телефон на тихий режим.",
                "Сделай 6 медленных выдохов. Выдох чуть длиннее вдоха.",
                "Расслабь плечи, челюсть и ладони.",
                common_end,
            ),
            RecommendationMode.SHORT_WIND_DOWN: (
                "Погаси лишний свет и убери дела из головы в одну короткую заметку.",
                "Дыши спокойно 2 минуты: вдох 4 счета, выдох 6 счетов.",
                "Проверь тело сверху вниз и отпусти напряжение.",
                common_end,
            ),
            RecommendationMode.STANDARD_WIND_DOWN: (
                "Сделай мягкий переход: свет ниже, уведомления выключены, вода рядом.",
                "Запиши одну мысль, которую не нужно решать ночью.",
                "5 минут спокойного дыхания без цели заснуть немедленно.",
                "Ляг удобно и возвращай внимание к выдоху.",
            ),
            RecommendationMode.CALM_NIGHT_PROTOCOL: (
                "Сначала снижаем стимулы: свет, звук, переписки и новости.",
                "Сделай короткий телесный скан: лоб, плечи, грудь, живот, ноги.",
                "Выбери один спокойный якорь: дыхание, тишина или ровный звук.",
                common_end,
            ),
            RecommendationMode.STRESS_DOWN_PROTOCOL: (
                "Сейчас задача не уснуть силой, а снизить напряжение.",
                "Запиши тревожную мысль одной строкой и рядом следующий маленький шаг на завтра.",
                "Дыши 3 минуты: вдох спокойно, выдох длиннее.",
                "Отпусти контроль результата. Достаточно просто лежать спокойно.",
            ),
            RecommendationMode.LOW_ENERGY_GENTLE_SLEEP: (
                "Ты уже уставший, поэтому делаем минимальный сценарий без нагрузки.",
                "Убери экран, устройся удобно, не анализируй день.",
                "10 спокойных выдохов. Каждый следующий чуть мягче предыдущего.",
                common_end,
            ),
            RecommendationMode.LATE_NIGHT_QUICK_SHUTDOWN: (
                "Никаких длинных ритуалов. Только выключаем лишние стимулы.",
                "Поставь будильник, если нужен, и больше не проверяй время.",
                "Ляг удобно и держи внимание на медленном выдохе.",
            ),
            RecommendationMode.RECOVERY_BREAK: (
                "Это короткое восстановление, не попытка обязательно уснуть.",
                "Сядь или ляг удобно, закрой глаза на несколько минут.",
                "Сделай медленные выдохи и не открывай ленты/чаты.",
            ),
            RecommendationMode.GUIDED_NAP_ATTEMPT: (
                "Поставь мягкий будильник и дай себе право просто отдохнуть.",
                "Первые 2 минуты расслабь лицо, плечи и живот.",
                "Если сон не пришел, отдых все равно засчитывается.",
            ),
            RecommendationMode.LONG_REST_SESSION: (
                "Окно длинное, но днем лучше не уходить слишком глубоко без причины.",
                "Поставь будильник и выбери мягкий выход.",
                "После пробуждения дай себе 2-3 минуты на возвращение в активность.",
            ),
            RecommendationMode.POWER_NAP_10: (
                "10 минут - это быстрый сброс напряжения, не полноценный сон.",
                "Закрой глаза, убери звук уведомлений, расслабь плечи.",
                "После сигнала сразу сядь и сделай несколько глубоких вдохов.",
            ),
            RecommendationMode.POWER_NAP_15: (
                "15 минут - хороший баланс между отдыхом и быстрым возвращением.",
                "Поставь будильник, затем 1 минуту спокойно выдыхай.",
                "После сигнала встань без повторного откладывания.",
            ),
            RecommendationMode.POWER_NAP_20: (
                "20 минут - максимум для короткого сна без сильной инерции.",
                "Подготовь мягкий выход: свет, вода, короткая разминка после сигнала.",
                "Если не заснул, это все равно был восстановительный перерыв.",
            ),
        }
        steps = steps_by_mode[mode]
        if is_premium and request.mode != SleepMode.POWER_NAP:
            steps = (*steps, "Premium: завтра бот сравнит этот сценарий с твоей историей и предложит более точную настройку.")
        return steps

    def _follow_up_minutes(self, mode: RecommendationMode) -> int | None:
        if mode in {RecommendationMode.POWER_NAP_10, RecommendationMode.POWER_NAP_15, RecommendationMode.POWER_NAP_20}:
            return 5
        if mode in {RecommendationMode.RECOVERY_BREAK, RecommendationMode.GUIDED_NAP_ATTEMPT, RecommendationMode.LONG_REST_SESSION}:
            return 10
        return None

    def _power_nap_duration(self, free_minutes: int, default_duration: int) -> int:
        if free_minutes < 13:
            return 10
        if free_minutes < 18:
            return 15
        if default_duration in {10, 15, 20} and default_duration <= free_minutes:
            return default_duration
        return 20

    def _is_late_night(self, moment: datetime) -> bool:
        return moment.hour >= 1 or moment.hour <= 4

    def _short_flow_bias(self, history: tuple[SleepEntry, ...]) -> bool:
        if len(history) < 3:
            return False
        short_entries = [entry for entry in history if entry.duration_minutes <= 12]
        long_entries = [entry for entry in history if entry.duration_minutes > 12]
        if not short_entries or not long_entries:
            return False
        short_score = sum(entry.helpfulness for entry in short_entries) / len(short_entries)
        long_score = sum(entry.helpfulness for entry in long_entries) / len(long_entries)
        return short_score >= long_score + 1

    def _noise_performed_poorly(self, history: tuple[SleepEntry, ...]) -> bool:
        noise_entries = [entry for entry in history if entry.audio_used in {AudioType.WHITE_NOISE, AudioType.PINK_NOISE}]
        if len(noise_entries) < 2:
            return False
        return sum(entry.helpfulness for entry in noise_entries) / len(noise_entries) <= 2.5
