from __future__ import annotations

from apps.bot.app.local_bot import LocalBotSession


def test_local_bot_demo_flow() -> None:
    session = LocalBotSession(telegram_id=500, username="demo")

    session.start()
    text = session.demo_night_flow()
    session.wake_checkin()

    assert "Режим:" in text
    assert len(session.messages) == 4
