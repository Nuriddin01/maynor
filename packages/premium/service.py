from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.billing.service import BillingService
from packages.core.config import get_settings
from packages.domain.models import AudioType, Recommendation, SleepEntry


@dataclass(frozen=True)
class PremiumRoutine:
  id: int
  user_id: UUID
  title: str
  routine_type: str
  duration_minutes: int
  steps: tuple[str, ...]
  created_at: datetime


class PremiumExperienceService:
  def __init__(self, store: Any, billing: BillingService, db_path: str | None = None) -> None:
    self.store = store
    self.billing = billing
    self.db_path = db_path or get_settings().local_db_path
    self._ensure_schema()

  def is_premium(self, user_id: UUID) -> bool:
    return self.billing.has_feature(user_id, "advanced_analytics")

  def active_features(self, user_id: UUID) -> frozenset[str]:
    return self.billing.active_features(user_id)

  def status_text(self, user_id: UUID) -> str:
    subscription = self.billing._store.get_subscription(user_id)
    if subscription is None or not self.is_premium(user_id):
      return (
        "⭐ Premium не активен\n\n"
        "Premium открывает weekly insights, deep history, advanced stats, content packs, "
        "custom routines и расширенную библиотеку сопровождения."
      )
    return (
      "⭐ Premium активен ✅\n\n"
      f"Тариф: {subscription.plan_code}\n"
      f"Доступ до: {subscription.current_period_end.strftime('%d.%m.%Y')}\n"
      "Доступны: weekly insights, deep history, advanced analytics, content packs, custom routines."
    )

  def paywall_text(self, feature_title: str) -> str:
    return (
      f"⭐ {feature_title} доступен в Premium.\n\n"
      "Это расширенная функция: она использует историю, предпочтения и больше контента.\n"
      "Открой «⭐ Premium», чтобы подключить доступ через Telegram Stars."
    )

  def weekly_insights_text(self, user_id: UUID) -> str:
    entries = self._entries(user_id)[-7:]
    recommendations = self._recommendations(user_id)[-20:]
    if not entries and not recommendations:
      return (
        "📅 Weekly insights\n\n"
        "Пока мало данных для недельного вывода. Используй check-in после сна хотя бы 2-3 раза - "
        "после этого здесь появятся устойчивые наблюдения."
      )

    avg_sleep = self._avg([entry.duration_minutes for entry in entries])
    avg_quality = self._avg([entry.quality for entry in entries])
    avg_feeling = self._avg([entry.post_wake_feeling for entry in entries])
    helpful_modes = self._helpful_modes(user_id)
    mode_line = helpful_modes[0] if helpful_modes else "пока нет явного лидера"
    debt = self._sleep_debt(entries, target=480)

    lines = [
      "📅 Weekly insights",
      "",
      f"Записей сна за неделю: {len(entries)}",
      f"Средняя длительность: {self._minutes(avg_sleep)}",
      f"Среднее качество: {self._score(avg_quality)}",
      f"Самочувствие после сна: {self._score(avg_feeling)}",
      f"Оценочный долг сна: {debt} мин",
      f"Самый полезный формат по оценкам: {mode_line}",
      "",
      "Мягкий вывод:",
      self._weekly_conclusion(avg_sleep, avg_quality, avg_feeling, debt),
      "",
      "Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, обратитесь к специалисту.",
    ]
    return "\n".join(lines)

  def advanced_stats_text(self, user_id: UUID) -> str:
    entries = self._entries(user_id)
    recommendations = self._recommendations(user_id)
    feedback = self.store.recommendation_feedback.get(user_id, [])
    if not entries and not recommendations:
      return "📈 Advanced stats\n\nПока мало данных. Пройди 2-3 сценария и check-in после сна."

    last_30 = entries[-30:]
    avg_sleep = self._avg([entry.duration_minutes for entry in last_30])
    avg_quality = self._avg([entry.quality for entry in last_30])
    avg_helpfulness = self._avg([entry.helpfulness for entry in last_30])
    completion_basis = len(feedback) + len(entries)
    disliked_audio = self._disliked_audio(user_id)
    top_audio = self._top_audio(entries)
    top_modes = self._top_recommendation_modes(recommendations)

    return (
      "📈 Advanced stats\n\n"
      f"Период: последние 30 записей\n"
      f"Средняя длительность сна: {self._minutes(avg_sleep)}\n"
      f"Среднее качество: {self._score(avg_quality)}\n"
      f"Средняя полезность: {self._score(avg_helpfulness)}\n"
      f"Сценариев в истории: {len(recommendations)}\n"
      f"Оценок/завершений: {completion_basis}\n"
      f"Частый аудио-формат: {top_audio}\n"
      f"Форматы, которые лучше не предлагать часто: {disliked_audio}\n"
      f"Топ сценарии: {top_modes}\n\n"
      "Интерпретация: это субъективная аналитика по твоим check-in, а не медицинская диагностика."
    )

  def deep_history_text(self, user_id: UUID, limit: int = 15) -> str:
    entries = self._entries(user_id)[-limit:]
    recommendations = self._recommendations(user_id)[-limit:]
    if not entries and not recommendations:
      return "📚 Deep history\n\nИстория пока пустая."

    lines = ["📚 Deep history", ""]
    if entries:
      lines.append("Check-ins:")
      for entry in reversed(entries[-10:]):
        lines.append(
          f"- {entry.created_at.strftime('%d.%m %H:%M')}: "
          f"сон {entry.duration_minutes} мин, качество {entry.quality}/5, "
          f"самочувствие {entry.post_wake_feeling}/5, польза {entry.helpfulness}/5"
        )
    if recommendations:
      lines.extend(["", "Рекомендации:"])
      for rec in reversed(recommendations[-10:]):
        lines.append(
          f"- {rec.created_at.strftime('%d.%m %H:%M')}: {rec.recommended_mode.value}, "
          f"{rec.duration_minutes} мин, аудио {rec.audio.value}"
        )
    return "\n".join(lines)

  def content_packs_text(self, user_id: UUID) -> str:
    return (
      "🎧 Premium content packs\n\n"
      "1. Calm Night Pack\n"
      "- короткий протокол для спокойного завершения дня\n"
      "- мягкий текст-гайд без псевдонауки\n\n"
      "2. Focus Recovery Pack\n"
      "- 5-15 минут восстановления после нагрузки\n"
      "- подходит для дневного перерыва\n\n"
      "3. Low Energy Pack\n"
      "- бережный сценарий, когда сил мало\n"
      "- без давления и токсичной мотивации\n\n"
      "Нажми «🧩 Custom routine», чтобы собрать персональную рутину из этих блоков."
    )

  def audio_library_text(self, user_id: UUID) -> str:
    return (
      "🔊 Premium audio library\n\n"
      "Доступные форматы сопровождения:\n"
      "- Без аудио\n"
      "- Тишина\n"
      "- Дождь\n"
      "- Лес\n"
      "- Pink noise\n"
      "- Только дыхание\n"
      "- Текст-гайд\n\n"
      "Если какой-то формат раздражает, укажи это в check-in - бот будет реже его предлагать.\n"
      "Сейчас это контентный модуль с metadata/placeholders, готовый к подключению настоящих файлов."
    )

  def experiments_text(self, user_id: UUID) -> str:
    return (
      "🧪 Premium experiments\n\n"
      "Активные безопасные эксперименты:\n"
      "- shorter_evening_flow: бот чаще предлагает короткие вечерние сценарии, если пользователь бросает длинные\n"
      "- audio_dislike_guard: раздражающие аудио-форматы уходят из рекомендаций\n"
      "- weekly_soft_insight: раз в неделю формируется спокойный вывод по истории\n\n"
      "Эксперименты не дают медицинских советов и не меняют дисклеймеры."
    )

  def create_routine(self, user_id: UUID, routine_type: str, duration_minutes: int) -> PremiumRoutine:
    if routine_type not in {"evening", "morning", "nap"}:
      raise ValueError("unknown routine type")
    if not 5 <= duration_minutes <= 60:
      raise ValueError("duration must be between 5 and 60")
    title, steps = self._routine_template(routine_type, duration_minutes)
    now = datetime.now(timezone.utc)
    with self._connect() as connection:
      cursor = connection.execute(
        """
        INSERT INTO premium_routines(user_id, title, routine_type, duration_minutes, steps_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(user_id), title, routine_type, duration_minutes, json.dumps(list(steps), ensure_ascii=False), now.isoformat()),
      )
      routine_id = int(cursor.lastrowid)
    return PremiumRoutine(routine_id, user_id, title, routine_type, duration_minutes, steps, now)

  def routines_text(self, user_id: UUID) -> str:
    routines = self.list_routines(user_id)
    if not routines:
      return (
        "🧩 Custom routines\n\n"
        "Пока нет сохранённых рутин. Выбери тип: вечерняя, утренняя или power nap - и бот сохранит её локально."
      )
    lines = ["🧩 Custom routines", ""]
    for routine in routines[-5:]:
      lines.append(f"{routine.id}. {routine.title} - {routine.duration_minutes} мин")
      for index, step in enumerate(routine.steps, 1):
        lines.append(f"   {index}. {step}")
    return "\n".join(lines)

  def list_routines(self, user_id: UUID) -> list[PremiumRoutine]:
    with self._connect() as connection:
      rows = connection.execute(
        "SELECT * FROM premium_routines WHERE user_id = ? ORDER BY created_at DESC",
        (str(user_id),),
      ).fetchall()
    return [self._row_to_routine(row) for row in rows]

  def _ensure_schema(self) -> None:
    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    with self._connect() as connection:
      connection.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_routines (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          title TEXT NOT NULL,
          routine_type TEXT NOT NULL,
          duration_minutes INTEGER NOT NULL,
          steps_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
      )
      connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_premium_routines_user ON premium_routines(user_id, created_at)"
      )

  def _connect(self) -> sqlite3.Connection:
    connection = sqlite3.connect(self.db_path)
    connection.row_factory = sqlite3.Row
    return connection

  def _row_to_routine(self, row: sqlite3.Row) -> PremiumRoutine:
    return PremiumRoutine(
      id=int(row["id"]),
      user_id=UUID(row["user_id"]),
      title=row["title"],
      routine_type=row["routine_type"],
      duration_minutes=int(row["duration_minutes"]),
      steps=tuple(json.loads(row["steps_json"])),
      created_at=datetime.fromisoformat(row["created_at"]),
    )

  def _entries(self, user_id: UUID) -> list[SleepEntry]:
    return list(self.store.entries.get(user_id, []))

  def _recommendations(self, user_id: UUID) -> list[Recommendation]:
    return list(self.store.recommendations.get(user_id, []))

  def _avg(self, values: list[int]) -> float | None:
    return None if not values else sum(values) / len(values)

  def _minutes(self, value: float | None) -> str:
    if value is None:
      return "нет данных"
    hours = int(value) // 60
    minutes = int(value) % 60
    return f"{hours} ч {minutes:02d} мин"

  def _score(self, value: float | None) -> str:
    return "нет данных" if value is None else f"{value:.1f}/5"

  def _sleep_debt(self, entries: list[SleepEntry], target: int) -> int:
    if not entries:
      return 0
    return max(0, sum(max(0, target - entry.duration_minutes) for entry in entries))

  def _weekly_conclusion(self, avg_sleep: float | None, avg_quality: float | None, avg_feeling: float | None, debt: int) -> str:
    if debt >= 240:
      return "Есть признаки накопленного недосыпа по твоим записям. На этой неделе лучше не усложнять рутину и выбрать более ранний отбой."
    if avg_quality is not None and avg_quality <= 2.5:
      return "Качество сна часто низкое. Лучше выбирать спокойные короткие сценарии и не перегружать вечер длинными инструкциями."
    if avg_feeling is not None and avg_feeling <= 2.5:
      return "После пробуждения энергии мало. Попробуй мягкое пробуждение и воду до сообщений."
    return "Картина выглядит ровной. Главная задача - сохранять стабильность и не делать вечернюю рутину слишком длинной."

  def _helpful_modes(self, user_id: UUID) -> list[str]:
    recommendations = {item.id: item for item in self._recommendations(user_id)}
    feedback = self.store.recommendation_feedback.get(user_id, [])
    scored: dict[str, list[int]] = {}
    for item in feedback:
      recommendation = recommendations.get(item.recommendation_id)
      if recommendation is None:
        continue
      scored.setdefault(recommendation.recommended_mode.value, []).append(item.helpfulness)
    averages = sorted(
      ((mode, sum(values) / len(values)) for mode, values in scored.items()),
      key=lambda item: item[1],
      reverse=True,
    )
    return [f"{mode} ({score:.1f}/5)" for mode, score in averages]

  def _disliked_audio(self, user_id: UUID) -> str:
    entries = self._entries(user_id)
    disliked = [entry.audio_used.value for entry in entries if entry.helpfulness <= 2]
    if not disliked:
      return "нет явных"
    return ", ".join(sorted(set(disliked)))

  def _top_audio(self, entries: list[SleepEntry]) -> str:
    if not entries:
      return "нет данных"
    counts: dict[str, int] = {}
    for entry in entries:
      counts[entry.audio_used.value] = counts.get(entry.audio_used.value, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]

  def _top_recommendation_modes(self, recommendations: list[Recommendation]) -> str:
    if not recommendations:
      return "нет данных"
    counts: dict[str, int] = {}
    for recommendation in recommendations:
      counts[recommendation.recommended_mode.value] = counts.get(recommendation.recommended_mode.value, 0) + 1
    top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:3]
    return ", ".join(f"{mode} ({count})" for mode, count in top)

  def _routine_template(self, routine_type: str, duration: int) -> tuple[str, tuple[str, ...]]:
    if routine_type == "evening":
      return (
        "Вечерняя рутина",
        (
          f"За {duration} минут до сна убери активные переписки и яркий экран.",
          "Подготовь воду, будильник и одно спокойное действие на утро.",
          "Сделай 6-8 спокойных выдохов длиннее вдоха.",
        ),
      )
    if routine_type == "morning":
      return (
        "Утренняя рутина",
        (
          "Сядь после сигнала и не открывай сообщения первые 2 минуты.",
          "Выпей воды и включи свет или подойди к окну.",
          f"Сделай {min(duration, 10)} минут мягкого старта: плечи, шея, стопы.",
        ),
      )
    return (
      "Power nap рутина",
      (
        f"Поставь таймер на {min(duration, 20)} минут.",
        "Убери уведомления и не пытайся заставить себя уснуть.",
        "После сигнала сядь, сделай пару вдохов и выпей воды.",
      ),
    )
