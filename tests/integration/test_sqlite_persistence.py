from __future__ import annotations

from packages.domain.models import AudioType
from packages.services.facade import AppServices


def test_sqlite_store_persists_users_entries_recommendations_and_alarms(tmp_path) -> None:
    db_path = tmp_path / "sleep.sqlite3"
    first = AppServices.local(str(db_path))
    user = first.start_user(telegram_id=777, username="persistent")
    first.accept_consents(user.id)
    first.generate_night_recommendation(user, 390, 3, 4, 5, 15, False, AudioType.RAIN)
    first.add_wake_checkin(user, 420, 4, 4, 4, AudioType.RAIN, "ok")
    first.create_power_nap_alarm(user, 15, "alarm-persistent")

    second = AppServices.local(str(db_path))
    restored = second.store.upsert_user(telegram_id=777)

    assert restored.id == user.id
    assert len(second.store.entries[user.id]) == 1
    assert len(second.store.recommendations[user.id]) == 1
    assert second.alarms._store.find_by_idempotency_key("alarm-persistent") is not None
