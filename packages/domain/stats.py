from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from packages.domain.models import AudioType, SleepEntry, SleepMode


@dataclass(frozen=True)
class SleepSummary:
    days: int
    entries_count: int
    average_duration: float | None
    average_quality: float | None
    average_post_wake_feeling: float | None
    most_effective_modes: tuple[str, ...]
    least_effective_modes: tuple[str, ...]
    streak_days: int
    possible_sleep_debt_minutes: int
    top_preferred_audio: AudioType | None
    completion_rate: float | None


class StatsService:
    def summarize(self, entries: tuple[SleepEntry, ...], now: datetime, days: int, started_flows: int | None = None) -> SleepSummary:
        since = now - timedelta(days=days)
        scoped = [entry for entry in entries if entry.created_at >= since]
        if not scoped:
            return SleepSummary(days, 0, None, None, None, (), (), 0, 0, None, None)
        avg_duration = self._avg(entry.duration_minutes for entry in scoped)
        avg_quality = self._avg(entry.quality for entry in scoped)
        avg_feeling = self._avg(entry.post_wake_feeling for entry in scoped)
        by_mode: dict[SleepMode, list[int]] = defaultdict(list)
        for entry in scoped:
            by_mode[entry.mode].append(entry.helpfulness)
        ranked = sorted(by_mode.items(), key=lambda item: sum(item[1]) / len(item[1]), reverse=True)
        most = tuple(item[0].value for item in ranked[:3])
        least = tuple(item[0].value for item in ranked[-3:])
        streak = self._streak_days(scoped, now)
        debt = self._sleep_debt(scoped)
        audio_counter = Counter(entry.audio_used for entry in scoped)
        top_audio = audio_counter.most_common(1)[0][0]
        completion_rate = None if not started_flows else min(1.0, len(scoped) / started_flows)
        return SleepSummary(
            days=days,
            entries_count=len(scoped),
            average_duration=round(avg_duration, 1),
            average_quality=round(avg_quality, 2),
            average_post_wake_feeling=round(avg_feeling, 2),
            most_effective_modes=most,
            least_effective_modes=least,
            streak_days=streak,
            possible_sleep_debt_minutes=debt,
            top_preferred_audio=top_audio,
            completion_rate=completion_rate,
        )

    def _avg(self, values: object) -> float:
        materialized = list(values)
        return sum(materialized) / len(materialized)

    def _streak_days(self, entries: list[SleepEntry], now: datetime) -> int:
        dates = {entry.created_at.date() for entry in entries}
        streak = 0
        cursor = now.date()
        while cursor in dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def _sleep_debt(self, entries: list[SleepEntry]) -> int:
        night_entries = [entry for entry in entries if entry.mode == SleepMode.NIGHT_SLEEP]
        if not night_entries:
            return 0
        target = 7 * 60
        return sum(max(0, target - entry.duration_minutes) for entry in night_entries)
