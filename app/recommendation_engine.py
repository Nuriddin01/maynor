from __future__ import annotations

from collections import Counter

from app.constants import SCENARIO_LIBRARY, THRESHOLDS
from app.schemas import HistoricalSignal, RecommendationOutput, RecommendationRequest


class RecommendationEngine:
    """Transparent heuristic engine without medical claims."""

    def build_recommendation(self, payload: RecommendationRequest) -> RecommendationOutput:
        history_snapshot = self._build_history_snapshot(payload.history)

        if payload.request_type == "night":
            mode, duration = self._recommend_night(payload, history_snapshot)
        elif payload.request_type == "day":
            mode, duration = self._recommend_day(payload, history_snapshot)
        else:
            mode, duration = self._recommend_power_nap(payload, history_snapshot)

        scenario = SCENARIO_LIBRARY[mode]
        audio = self._pick_audio(payload, scenario.default_audio_type, history_snapshot)
        confidence = self._build_confidence_label(payload, history_snapshot)
        explanation = self._build_explanation(payload, mode, history_snapshot)

        return RecommendationOutput(
            recommended_mode=mode,
            recommended_duration_minutes=duration,
            explanation_for_user=explanation,
            steps=scenario.steps,
            breathing_practice=scenario.breathing_practice,
            relaxation_tip=scenario.relaxation_tip,
            sleep_hygiene_tip=scenario.sleep_hygiene_tip,
            optional_audio_type=audio,
            suggest_alarm=payload.request_type in {"day", "power_nap"} and duration is not None,
            confidence_label=confidence,
            followup_hint=scenario.followup_hint,
        )

    def _recommend_night(self, payload: RecommendationRequest, history: dict) -> tuple[str, int]:
        free_time = payload.free_time_minutes
        high_stress = (payload.current_stress or 0) >= THRESHOLDS["high_stress_score"]
        poor_recent_sleep = history["avg_duration"] is not None and history["avg_duration"] < THRESHOLDS["chronic_sleep_debt_avg_minutes"]
        low_quality = (payload.subjective_sleep_quality or 3) <= THRESHOLDS["low_quality_score"]

        if free_time <= THRESHOLDS["night_ultra_short_max"]:
            return "ultra_short_wind_down", free_time
        if high_stress and free_time >= 10:
            return "calm_night_protocol", min(free_time, 25)
        if free_time <= THRESHOLDS["night_short_max"]:
            return "short_wind_down", free_time
        if poor_recent_sleep or low_quality:
            return "calm_night_protocol", min(free_time, 30)
        if free_time <= THRESHOLDS["night_standard_max"]:
            return "standard_wind_down", min(free_time, 25)
        return "calm_night_protocol", min(free_time, 30)

    def _recommend_day(self, payload: RecommendationRequest, history: dict) -> tuple[str, int]:
        free_time = payload.free_time_minutes
        wants_sleep = (payload.mode_preference or "").lower() == "sleep"
        sleepy = (payload.current_sleepiness or 0) >= 4
        high_stress = (payload.current_stress or 0) >= THRESHOLDS["high_stress_score"]
        poor_recent_sleep = history["avg_duration"] is not None and history["avg_duration"] < THRESHOLDS["chronic_sleep_debt_avg_minutes"]

        if free_time <= THRESHOLDS["day_recovery_max"]:
            return "recovery_break", min(free_time, 8)

        if high_stress and not wants_sleep:
            return "short_day_rest", min(free_time, 15)

        if free_time <= 20:
            if wants_sleep or sleepy or poor_recent_sleep:
                return "guided_nap_attempt", min(free_time, 20)
            return "short_day_rest", min(free_time, 15)

        if free_time <= THRESHOLDS["day_short_rest_max"]:
            if wants_sleep or sleepy:
                return "guided_nap_attempt", min(free_time, 25)
            return "short_day_rest", min(free_time, 20)

        return "long_rest_session", min(free_time, 45)

    def _recommend_power_nap(self, payload: RecommendationRequest, history: dict) -> tuple[str, int]:
        free_time = payload.free_time_minutes
        sleepy = payload.current_sleepiness or 3
        poor_recent_sleep = history["avg_duration"] is not None and history["avg_duration"] < THRESHOLDS["chronic_sleep_debt_avg_minutes"]

        if free_time < THRESHOLDS["power_nap_min"]:
            return "recovery_break", min(free_time, 8)
        if free_time < THRESHOLDS["power_nap_medium"]:
            return "power_nap_10", 10
        if free_time < THRESHOLDS["power_nap_max"] or sleepy <= 3:
            return "power_nap_15", 15
        if poor_recent_sleep or sleepy >= 4:
            return "power_nap_20", 20
        return "power_nap_15", 15

    def _build_history_snapshot(self, history: list[HistoricalSignal]) -> dict:
        if not history:
            return {
                "avg_duration": None,
                "avg_helpfulness": None,
                "helpful_modes": [],
            }

        durations = [entry.duration_minutes for entry in history]
        helpfulness_values = [entry.helpfulness_1_5 for entry in history if entry.helpfulness_1_5 is not None]
        helpful_counter = Counter(
            entry.mode
            for entry in history
            if entry.helpfulness_1_5 is not None and entry.helpfulness_1_5 >= 4
        )

        return {
            "avg_duration": sum(durations) / len(durations),
            "avg_helpfulness": (
                sum(helpfulness_values) / len(helpfulness_values)
                if helpfulness_values
                else None
            ),
            "helpful_modes": [mode for mode, _ in helpful_counter.most_common(2)],
        }

    def _pick_audio(self, payload: RecommendationRequest, default_audio: str | None, history: dict) -> str | None:
        if payload.preferred_audio and not (
            payload.preferred_audio == "white_noise" and payload.dislikes_white_noise
        ):
            return payload.preferred_audio

        preference_priority: list[str] = []
        if payload.likes_silence:
            preference_priority.append("silence")
        if payload.likes_rain:
            preference_priority.append("rain")
        if payload.likes_forest:
            preference_priority.append("forest")

        if default_audio == "white_noise" and payload.dislikes_white_noise:
            default_audio = "rain" if payload.likes_rain else "forest"

        if preference_priority:
            if default_audio in preference_priority:
                return default_audio
            return preference_priority[0]

        if default_audio == "white_noise" and payload.dislikes_white_noise:
            return "silence"
        return default_audio

    def _build_confidence_label(self, payload: RecommendationRequest, history: dict) -> str:
        signal_count = 0
        if payload.subjective_sleep_quality is not None:
            signal_count += 1
        if payload.current_sleepiness is not None:
            signal_count += 1
        if payload.current_stress is not None:
            signal_count += 1
        if history["avg_duration"] is not None:
            signal_count += 1

        if signal_count >= 4:
            return "high"
        if signal_count >= 2:
            return "medium"
        return "low"

    def _build_explanation(self, payload: RecommendationRequest, mode: str, history: dict) -> str:
        reasons: list[str] = []
        if payload.slept_last_night_minutes < THRESHOLDS["recommended_sleep_min"]:
            reasons.append("прошлая ночь была короче условного восстановительного диапазона")
        if (payload.current_stress or 0) >= THRESHOLDS["high_stress_score"]:
            reasons.append("сейчас заметно напряжение")
        if payload.free_time_minutes <= THRESHOLDS["day_recovery_max"]:
            reasons.append("свободное окно очень короткое")
        if history["helpful_modes"]:
            reasons.append(
                f"в недавней истории вам чаще помогали похожие форматы: {', '.join(history['helpful_modes'])}"
            )

        if not reasons:
            reasons.append("выбран спокойный и реалистичный сценарий под текущее окно времени")

        return (
            f"Я выбрал режим {mode} потому, что "
            + "; ".join(reasons)
            + ". Это мягкая рекомендация, а не строгая норма."
        )
