from datetime import datetime, timezone

from app.recommendation_engine import RecommendationEngine
from app.schemas import HistoricalSignal, RecommendationRequest


def test_night_high_stress_prefers_calm_protocol() -> None:
    engine = RecommendationEngine()
    payload = RecommendationRequest(
        request_type="night",
        slept_last_night_minutes=310,
        subjective_sleep_quality=2,
        current_sleepiness=4,
        current_stress=5,
        free_time_minutes=20,
    )

    result = engine.build_recommendation(payload)

    assert result.recommended_mode == "calm_night_protocol"
    assert result.recommended_duration_minutes == 20
    assert result.confidence_label in {"medium", "high"}


def test_day_short_window_returns_recovery_break() -> None:
    engine = RecommendationEngine()
    payload = RecommendationRequest(
        request_type="day",
        slept_last_night_minutes=360,
        current_energy=2,
        current_sleepiness=4,
        current_stress=3,
        free_time_minutes=8,
        mode_preference="recovery",
    )

    result = engine.build_recommendation(payload)

    assert result.recommended_mode == "recovery_break"
    assert result.recommended_duration_minutes == 8


def test_power_nap_uses_20_minutes_for_sleep_debt() -> None:
    engine = RecommendationEngine()
    history = [
        HistoricalSignal(
            mode="guided_nap_attempt",
            duration_minutes=25,
            subjective_sleep_quality_1_5=3,
            felt_after_waking_1_5=4,
            helpfulness_1_5=4,
            created_at=datetime.now(timezone.utc),
        )
    ]
    payload = RecommendationRequest(
        request_type="power_nap",
        slept_last_night_minutes=290,
        current_sleepiness=5,
        free_time_minutes=25,
        history=history,
        preferred_audio="white_noise",
        dislikes_white_noise=True,
        likes_rain=True,
    )

    result = engine.build_recommendation(payload)

    assert result.recommended_mode == "power_nap_20"
    assert result.optional_audio_type != "white_noise"
