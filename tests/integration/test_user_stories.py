from __future__ import annotations

from datetime import time

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from packages.domain.models import AudioType
from packages.services.facade import AppServices


def test_user_story_1_bedtime_plan_uses_profile_history_and_saves_result(tmp_path) -> None:
    services = AppServices.local(str(tmp_path / "story1.sqlite3"))
    user = services.start_user(telegram_id=1001, username="student")
    user = services.update_profile(user, wake_time=time(7, 30), timezone_name="UTC", target_sleep_minutes=480)
    services.add_wake_checkin(user, slept_minutes=390, quality=3, feeling=3, helpfulness=4, audio=AudioType.SILENCE, note=None)

    recommendation = services.generate_bedtime_plan(user, reminder_enabled=True)
    history = services.history(user.id)

    assert recommendation.request_mode == "bedtime_planning"
    assert recommendation.snapshot["sleep_debt_minutes"] == 90
    assert recommendation.snapshot["recommended_bedtime"] == "23:00"
    assert recommendation.snapshot["target_wake_time"] == "07:30"
    assert recommendation.snapshot["baseline_used"] is False
    assert recommendation.snapshot["reminder_offer"] is True
    assert len(history["recommendations"]) == 1


def test_user_story_1_bedtime_plan_falls_back_to_baseline_without_history(tmp_path) -> None:
    services = AppServices.local(str(tmp_path / "story1_baseline.sqlite3"))
    user = services.start_user(telegram_id=1002, username="student")

    recommendation = services.generate_bedtime_plan(user, reminder_enabled=False)

    assert recommendation.snapshot["baseline_used"] is True
    assert "Данных пока мало" in recommendation.steps[0]


def test_user_story_2_day_recovery_supports_power_nap_and_meditation(tmp_path) -> None:
    services = AppServices.local(str(tmp_path / "story2.sqlite3"))
    user = services.start_user(telegram_id=2001, username="worker")
    user = services.update_profile(user, wake_time=time(8, 0), target_sleep_minutes=480)
    services.add_wake_checkin(user, 360, 3, 3, 4, AudioType.SILENCE, None)

    nap = services.generate_day_recovery(user, choice="power_nap", free_minutes=None, reminder_enabled=True)
    meditation = services.generate_day_recovery(user, choice="meditation", free_minutes=None, reminder_enabled=True)

    assert nap.request_mode == "power_nap"
    assert nap.duration_minutes in {10, 15, 20}
    assert nap.snapshot["sleep_debt_minutes"] == 120
    assert nap.snapshot["reminder_offer"] is True
    assert meditation.request_mode == "meditation"
    assert meditation.recommended_mode in {"meditation_10", "meditation_15"}
    assert len(services.history(user.id)["recommendations"]) == 2


def test_user_story_2_day_recovery_marks_need_for_time_input_when_data_is_missing(tmp_path) -> None:
    services = AppServices.local(str(tmp_path / "story2_missing.sqlite3"))
    user = services.start_user(telegram_id=2002, username="worker")

    result = services.generate_day_recovery(user, choice="meditation", free_minutes=12, reminder_enabled=False)

    assert result.snapshot["needs_free_time_input"] is True
    assert result.duration_minutes == 10


def test_user_story_3_sleep_and_wake_techniques_save_feedback(tmp_path) -> None:
    services = AppServices.local(str(tmp_path / "story3.sqlite3"))
    user = services.start_user(telegram_id=3001, username="sleepy")
    user = services.update_profile(user, wake_time=time(6, 30), target_sleep_minutes=480)
    services.add_wake_checkin(user, 330, 2, 2, 3, AudioType.SILENCE, None)

    quick_sleep = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=None, wake_feeling=None)
    good_wake = services.generate_sleep_or_wake_technique(user, kind="good_wake", quality=None, wake_feeling=None)
    feedback = services.add_recommendation_feedback(user, quick_sleep.id, helpfulness=5, note="helped")

    assert quick_sleep.request_mode == "quick_sleep_technique"
    assert quick_sleep.recommended_mode == "quick_sleep_body_scan"
    assert good_wake.request_mode == "good_wake_technique"
    assert good_wake.snapshot["feedback_prompt"]
    assert feedback.helpfulness == 5
    assert len(services.history(user.id)["recommendation_feedback"]) == 1


def test_api_exposes_user_story_endpoints() -> None:
    client = TestClient(create_app())
    client.post("/users/start", json={"telegram_id": 4001, "username": "api"})
    profile = client.put(
        "/users/4001/profile",
        json={"wake_time": "07:30", "timezone": "UTC", "target_sleep_minutes": 480, "default_nap_duration": 15},
    )
    assert profile.status_code == 200
    client.post(
        "/checkins/wake",
        json={"telegram_id": 4001, "slept_minutes": 390, "quality": 3, "feeling": 3, "helpfulness": 4, "audio": "silence"},
    )

    bedtime = client.post("/planning/bedtime", json={"telegram_id": 4001, "reminder_enabled": True})
    day = client.post("/recommendations/day-recovery", json={"telegram_id": 4001, "choice": "meditation", "reminder_enabled": True})
    technique = client.post("/recommendations/sleep-technique", json={"telegram_id": 4001, "kind": "good_wake"})
    history = client.get("/users/4001/history")

    assert bedtime.status_code == 200
    assert bedtime.json()["snapshot"]["recommended_bedtime"] == "23:00"
    assert day.status_code == 200
    assert day.json()["request_mode"] == "meditation"
    assert technique.status_code == 200
    assert technique.json()["request_mode"] == "good_wake_technique"
    assert len(history.json()["recommendations"]) >= 3
