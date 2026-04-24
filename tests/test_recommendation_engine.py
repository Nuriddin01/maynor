from app.recommendation_engine import RecommendationEngine
from app.schemas import RecommendationRequest


def test_power_nap_20_when_sleepy_and_has_time() -> None:
    engine = RecommendationEngine()
    out = engine.build_recommendation(
        RecommendationRequest(
            request_type="power_nap",
            slept_last_night_minutes=280,
            current_sleepiness=5,
            free_time_minutes=20,
        )
    )
    assert out.recommended_mode == "power_nap_20"


def test_recovery_break_when_short_time() -> None:
    engine = RecommendationEngine()
    out = engine.build_recommendation(
        RecommendationRequest(
            request_type="day",
            slept_last_night_minutes=400,
            current_energy=2,
            current_sleepiness=4,
            current_stress=3,
            free_time_minutes=8,
        )
    )
    assert out.recommended_mode == "recovery_break"


def test_high_stress_night_prefers_calm_protocol() -> None:
    engine = RecommendationEngine()
    out = engine.build_recommendation(
        RecommendationRequest(
            request_type="night",
            slept_last_night_minutes=300,
            subjective_sleep_quality=2,
            current_sleepiness=4,
            current_stress=5,
            free_time_minutes=20,
        )
    )
    assert out.recommended_mode == "calm_night_protocol"
