from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from apps.bot.app.texts import CONSENT_TEXT, MAIN_MENU, recommendation_text
from packages.domain.models import AudioType
from packages.services.facade import services


@dataclass
class LocalBotSession:
    telegram_id: int
    username: str | None = None
    messages: list[str] = field(default_factory=list)

    def start(self) -> str:
        user = services.start_user(self.telegram_id, self.username)
        self.messages.append(CONSENT_TEXT)
        services.accept_consents(user.id)
        self.messages.append(MAIN_MENU)
        return self.messages[-1]

    def demo_night_flow(self) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_night_recommendation(
            user=user,
            slept_minutes=390,
            quality=3,
            sleepiness=4,
            stress=3,
            free_minutes=15,
            needs_alarm=True,
            preferred_audio=AudioType.SILENCE,
        )
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def calculate_bedtime(self) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_bedtime_plan(user, reminder_enabled=True)
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def meditation(self, free_minutes: int = 10) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_day_recovery(user, choice="meditation", free_minutes=free_minutes, reminder_enabled=True)
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def power_nap(self, free_minutes: int = 15) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_day_recovery(user, choice="power_nap", free_minutes=free_minutes, reminder_enabled=True)
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def quick_sleep(self, quality: int = 3) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_sleep_or_wake_technique(user, kind="quick_sleep", quality=quality, wake_feeling=None)
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def good_wake(self, wake_feeling: int = 3) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        recommendation = services.generate_sleep_or_wake_technique(user, kind="good_wake", quality=None, wake_feeling=wake_feeling)
        text = recommendation_text(recommendation)
        self.messages.append(text)
        return text

    def wake_checkin(self) -> str:
        user = services.store.upsert_user(self.telegram_id, self.username)
        services.add_wake_checkin(user, 420, 4, 4, 4, AudioType.SILENCE, "local demo")
        text = f"Записал check-in за {datetime.now(timezone.utc).date().isoformat()}"
        self.messages.append(text)
        return text
