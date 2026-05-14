from __future__ import annotations

from datetime import datetime, timezone

from packages.domain.models import AudioType, RecommendationMode, SleepMode, SleepRequest, UserPreferences, new_uuid
from packages.domain.recommendation_engine import RecommendationContext, RecommendationEngine


def test_high_stress_gets_stress_down_protocol() -> None:
    user_id = new_uuid()
    request = SleepRequest(
        user_id=user_id,
        mode=SleepMode.NIGHT_SLEEP,
        slept_last_night_minutes=420,
        quality=3,
        sleepiness=3,
        stress=5,
        free_minutes=20,
        needs_alarm=False,
        preferred_audio=AudioType.RAIN,
        created_at=datetime.now(timezone.utc),
    )

    result = RecommendationEngine().generate(RecommendationContext(request, UserPreferences()))

    assert result.recommended_mode == RecommendationMode.STRESS_DOWN_PROTOCOL
    assert result.duration_minutes == 20
    assert result.audio == AudioType.RAIN
    assert any(item.rule == "high_stress" for item in result.decision_trace)


def test_power_nap_uses_available_window() -> None:
    user_id = new_uuid()
    request = SleepRequest(
        user_id=user_id,
        mode=SleepMode.POWER_NAP,
        slept_last_night_minutes=360,
        quality=3,
        sleepiness=4,
        stress=2,
        free_minutes=12,
        needs_alarm=True,
        preferred_audio=AudioType.SILENCE,
        created_at=datetime.now(timezone.utc),
    )

    result = RecommendationEngine().generate(RecommendationContext(request, UserPreferences()))

    assert result.recommended_mode == RecommendationMode.POWER_NAP_10
    assert result.duration_minutes == 10
    assert result.should_create_alarm is True


def test_disliked_audio_falls_back_to_silence() -> None:
    user_id = new_uuid()
    request = SleepRequest(
        user_id=user_id,
        mode=SleepMode.NIGHT_SLEEP,
        slept_last_night_minutes=420,
        quality=3,
        sleepiness=2,
        stress=2,
        free_minutes=12,
        needs_alarm=False,
        preferred_audio=AudioType.WHITE_NOISE,
        created_at=datetime.now(timezone.utc),
    )

    result = RecommendationEngine().generate(
        RecommendationContext(request, UserPreferences(disliked_audio=(AudioType.WHITE_NOISE,)))
    )

    assert result.audio == AudioType.SILENCE
