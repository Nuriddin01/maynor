from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MODE_DISPLAY_NAMES, THRESHOLDS
from app.models import SleepEntry
from app.schemas import StatsSummary
from app.utils.time_utils import utc_now


class StatsService:
    async def build_summary(self, session: AsyncSession, user_id: int) -> StatsSummary:
        since_30 = utc_now() - timedelta(days=30)
        since_7 = utc_now() - timedelta(days=7)
        result = await session.execute(
            select(SleepEntry).where(SleepEntry.user_id == user_id, SleepEntry.created_at >= since_30)
        )
        entries = list(result.scalars().all())
        if not entries:
            return StatsSummary(pattern_insights=["Пока данных мало. Добавьте несколько check-in для первых инсайтов."])

        entries_7 = [e for e in entries if self._as_aware(e.created_at) >= since_7]
        durations_30 = [e.duration_minutes for e in entries]
        durations_7 = [e.duration_minutes for e in entries_7] or durations_30
        qualities_30 = [e.subjective_sleep_quality_1_5 for e in entries if e.subjective_sleep_quality_1_5 is not None]
        felt_30 = [e.felt_after_waking_1_5 for e in entries if e.felt_after_waking_1_5 is not None]

        mode_counter = Counter(e.mode for e in entries)
        helpful_mode_scores: dict[str, list[int]] = defaultdict(list)
        for entry in entries:
            if entry.helpfulness_1_5 is not None:
                helpful_mode_scores[entry.mode].append(entry.helpfulness_1_5)

        most_helpful = sorted(
            helpful_mode_scores.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            reverse=True,
        )

        insights = self._build_insights(entries, durations_30, qualities_30, felt_30, helpful_mode_scores)

        return StatsSummary(
            average_duration_minutes_last_7_days=round(sum(durations_7) / len(durations_7), 1) if durations_7 else None,
            average_duration_minutes_last_30_days=round(sum(durations_30) / len(durations_30), 1),
            average_sleep_quality_last_30_days=round(sum(qualities_30) / len(qualities_30), 1) if qualities_30 else None,
            average_felt_after_last_30_days=round(sum(felt_30) / len(felt_30), 1) if felt_30 else None,
            most_used_modes=[MODE_DISPLAY_NAMES.get(mode, mode) for mode, _ in mode_counter.most_common(3)],
            most_helpful_modes=[MODE_DISPLAY_NAMES.get(mode, mode) for mode, _ in most_helpful[:3]],
            pattern_insights=insights,
            entries_count_last_30_days=len(entries),
        )

    def _build_insights(self, entries: list[SleepEntry], durations: list[int], qualities: list[int], felt_after: list[int], helpful_mode_scores: dict[str, list[int]]) -> list[str]:
        insights: list[str] = []
        avg_duration = sum(durations) / len(durations)
        if avg_duration < THRESHOLDS["chronic_sleep_debt_avg_minutes"]:
            insights.append("Последние дни есть недосып по средней длительности сна.")
        if qualities and (sum(qualities) / len(qualities) <= 2.5):
            insights.append("Субъективное качество сна чаще низкое — полезно выбирать более мягкие протоколы.")
        if felt_after and (sum(felt_after) / len(felt_after) >= 4):
            insights.append("После пробуждения чаще хорошие оценки — текущий режим в целом рабочий.")
        if helpful_mode_scores:
            best_mode = max(helpful_mode_scores.items(), key=lambda item: sum(item[1]) / len(item[1]))[0]
            insights.append(f"Чаще помогает режим: {MODE_DISPLAY_NAMES.get(best_mode, best_mode)}.")
        if len(entries) < 5:
            insights.append("Выводы предварительные: данных пока немного.")
        return insights

    @staticmethod
    def _as_aware(value):
        if value.tzinfo is None:
            from datetime import timezone
            return value.replace(tzinfo=timezone.utc)
        return value
