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
        since = utc_now() - timedelta(days=7)
        result = await session.execute(
            select(SleepEntry)
            .where(SleepEntry.user_id == user_id, SleepEntry.created_at >= since)
            .order_by(SleepEntry.created_at.desc())
        )
        entries = list(result.scalars().all())
        if not entries:
            return StatsSummary(
                entries_count_last_7_days=0,
                pattern_insights=[
                    "Пока данных мало. Сохраните несколько check-in, и бот соберет первые мягкие выводы."
                ],
            )

        durations = [entry.duration_minutes for entry in entries]
        qualities = [entry.subjective_sleep_quality_1_5 for entry in entries if entry.subjective_sleep_quality_1_5]
        felt_after = [entry.felt_after_waking_1_5 for entry in entries if entry.felt_after_waking_1_5]

        mode_counter = Counter(entry.mode for entry in entries)
        helpful_mode_scores: dict[str, list[int]] = defaultdict(list)
        for entry in entries:
            if entry.helpfulness_1_5 is not None:
                helpful_mode_scores[entry.mode].append(entry.helpfulness_1_5)

        most_helpful = sorted(
            helpful_mode_scores.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            reverse=True,
        )

        insights = self._build_insights(entries, durations, qualities, felt_after, helpful_mode_scores)

        return StatsSummary(
            average_duration_minutes_last_7_days=round(sum(durations) / len(durations), 1),
            average_sleep_quality_last_7_days=round(sum(qualities) / len(qualities), 1) if qualities else None,
            average_felt_after_last_7_days=round(sum(felt_after) / len(felt_after), 1) if felt_after else None,
            most_used_modes=[
                MODE_DISPLAY_NAMES.get(mode, mode) for mode, _ in mode_counter.most_common(3)
            ],
            most_helpful_modes=[
                MODE_DISPLAY_NAMES.get(mode, mode) for mode, _ in most_helpful[:3]
            ],
            pattern_insights=insights,
            entries_count_last_7_days=len(entries),
        )

    def _build_insights(
        self,
        entries: list[SleepEntry],
        durations: list[int],
        qualities: list[int],
        felt_after: list[int],
        helpful_mode_scores: dict[str, list[int]],
    ) -> list[str]:
        insights: list[str] = []
        avg_duration = sum(durations) / len(durations)

        if avg_duration < THRESHOLDS["chronic_sleep_debt_avg_minutes"]:
            insights.append(
                "Средняя длительность за 7 дней получилась ниже 6 часов. Это повод бережно относиться к восстановлению и не ждать высокой бодрости по умолчанию."
            )
        elif avg_duration >= THRESHOLDS["recommended_sleep_min"]:
            insights.append(
                "По средней длительности у вас уже есть неплохая база. Здесь полезно смотреть, какие ритуалы повышают субъективное качество."
            )

        if qualities and sum(qualities) / len(qualities) <= 2.5:
            insights.append(
                "Субъективное качество сна пока невысокое. Лучше опираться на мягкие ритуалы снижения стресса, а не на жесткий контроль засыпания."
            )

        if felt_after and sum(felt_after) / len(felt_after) >= 4:
            insights.append(
                "По ощущениям после пробуждения картина неплохая. Попробуйте закреплять те сценарии, которые вы отмечаете как полезные."
            )

        if helpful_mode_scores:
            best_mode = max(helpful_mode_scores.items(), key=lambda item: sum(item[1]) / len(item[1]))[0]
            insights.append(
                f"Чаще всего лучше отзывался режим {MODE_DISPLAY_NAMES.get(best_mode, best_mode)}. Его можно использовать как базовый ориентир."
            )

        if len(entries) < 3:
            insights.append("Пока записей немного, поэтому выводы еще предварительные.")

        return insights
