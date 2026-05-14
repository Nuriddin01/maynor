from __future__ import annotations

from dataclasses import dataclass

from packages.domain.models import AudioType, RecommendationMode


@dataclass(frozen=True)
class ContentItem:
    slug: str
    title: str
    language: str
    type: str
    body: str
    audio_type: AudioType
    premium: bool
    tags: tuple[str, ...]


class ContentRegistry:
    def __init__(self, items: tuple[ContentItem, ...]) -> None:
        self._items = items

    def all(self) -> tuple[ContentItem, ...]:
        return self._items

    def find_for_mode(self, mode: RecommendationMode, language: str, premium_allowed: bool) -> ContentItem | None:
        for item in self._items:
            if mode.value in item.tags and item.language == language and (premium_allowed or not item.premium):
                return item
        for item in self._items:
            if item.language == language and (premium_allowed or not item.premium):
                return item
        return None


SEED_CONTENT = (
    ContentItem(
        slug="ru-calm-night-basic",
        title="Спокойная ночь",
        language="ru",
        type="text_protocol",
        body="Короткий сценарий: убери свет, выключи уведомления, сделай 10 медленных выдохов и отпусти ожидание результата.",
        audio_type=AudioType.SILENCE,
        premium=False,
        tags=(RecommendationMode.CALM_NIGHT_PROTOCOL.value, RecommendationMode.SHORT_WIND_DOWN.value),
    ),
    ContentItem(
        slug="ru-power-nap-basic",
        title="Power nap 15",
        language="ru",
        type="text_protocol",
        body="Поставь будильник на 15 минут, закрой глаза, расслабь лицо и плечи. После сигнала сразу сядь.",
        audio_type=AudioType.NO_AUDIO,
        premium=False,
        tags=(RecommendationMode.POWER_NAP_15.value, RecommendationMode.POWER_NAP_10.value, RecommendationMode.POWER_NAP_20.value),
    ),
    ContentItem(
        slug="ru-premium-stress-down",
        title="Снижение напряжения",
        language="ru",
        type="text_protocol",
        body="Запиши тревожную мысль, отдели факт от прогноза и выбери один маленький шаг на завтра. Сейчас задача - отдых.",
        audio_type=AudioType.GUIDED_TEXT,
        premium=True,
        tags=(RecommendationMode.STRESS_DOWN_PROTOCOL.value,),
    ),
)


def default_registry() -> ContentRegistry:
    return ContentRegistry(SEED_CONTENT)
