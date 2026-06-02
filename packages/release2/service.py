from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.core.config import get_settings
from packages.domain.models import Recommendation, SleepEntry


@dataclass(frozen=True)
class ReminderSettings:
  user_id: UUID
  notifications_enabled: bool = True
  bedtime_reminder_enabled: bool = True
  wake_checkin_enabled: bool = True
  day_recovery_enabled: bool = True
  focus_reminder_enabled: bool = False
  reminder_time: str = "22:30"
  updated_at: datetime | None = None


class Release2Service:
  def __init__(self, store: Any, db_path: str | None = None) -> None:
    self.store = store
    self.db_path = db_path or get_settings().local_db_path
    self._ensure_schema()

  def settings(self, user_id: UUID) -> ReminderSettings:
    with self._connect() as connection:
      row = connection.execute(
        "SELECT * FROM release2_reminder_settings WHERE user_id = ?",
        (str(user_id),),
      ).fetchone()
    if row is None:
      return ReminderSettings(user_id=user_id, updated_at=datetime.now(timezone.utc))
    return ReminderSettings(
      user_id=UUID(row["user_id"]),
      notifications_enabled=bool(row["notifications_enabled"]),
      bedtime_reminder_enabled=bool(row["bedtime_reminder_enabled"]),
      wake_checkin_enabled=bool(row["wake_checkin_enabled"]),
      day_recovery_enabled=bool(row["day_recovery_enabled"]),
      focus_reminder_enabled=bool(row["focus_reminder_enabled"]),
      reminder_time=row["reminder_time"],
      updated_at=datetime.fromisoformat(row["updated_at"]),
    )

  def toggle(self, user_id: UUID, field: str) -> ReminderSettings:
    allowed = {
      "notifications_enabled",
      "bedtime_reminder_enabled",
      "wake_checkin_enabled",
      "day_recovery_enabled",
      "focus_reminder_enabled",
    }
    if field not in allowed:
      raise ValueError("unknown reminder setting")
    current = self.settings(user_id)
    data = current.__dict__.copy()
    data[field] = not bool(data[field])
    updated = ReminderSettings(**data, updated_at=datetime.now(timezone.utc))
    self.save_settings(updated)
    return updated

  def set_reminder_time(self, user_id: UUID, reminder_time: str) -> ReminderSettings:
    current = self.settings(user_id)
    updated = ReminderSettings(
      user_id=user_id,
      notifications_enabled=current.notifications_enabled,
      bedtime_reminder_enabled=current.bedtime_reminder_enabled,
      wake_checkin_enabled=current.wake_checkin_enabled,
      day_recovery_enabled=current.day_recovery_enabled,
      focus_reminder_enabled=current.focus_reminder_enabled,
      reminder_time=reminder_time,
      updated_at=datetime.now(timezone.utc),
    )
    self.save_settings(updated)
    return updated

  def save_settings(self, settings: ReminderSettings) -> None:
    with self._connect() as connection:
      connection.execute(
        """
        INSERT INTO release2_reminder_settings(
          user_id, notifications_enabled, bedtime_reminder_enabled, wake_checkin_enabled,
          day_recovery_enabled, focus_reminder_enabled, reminder_time, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          notifications_enabled = excluded.notifications_enabled,
          bedtime_reminder_enabled = excluded.bedtime_reminder_enabled,
          wake_checkin_enabled = excluded.wake_checkin_enabled,
          day_recovery_enabled = excluded.day_recovery_enabled,
          focus_reminder_enabled = excluded.focus_reminder_enabled,
          reminder_time = excluded.reminder_time,
          updated_at = excluded.updated_at
        """,
        (
          str(settings.user_id),
          int(settings.notifications_enabled),
          int(settings.bedtime_reminder_enabled),
          int(settings.wake_checkin_enabled),
          int(settings.day_recovery_enabled),
          int(settings.focus_reminder_enabled),
          settings.reminder_time,
          (settings.updated_at or datetime.now(timezone.utc)).isoformat(),
        ),
      )

  def reminders_text(self, user_id: UUID) -> str:
    settings = self.settings(user_id)
    return (
      "🔔 Напоминания\n\n"
      f"Общие уведомления: {self._on(settings.notifications_enabled)}\n"
      f"Вечерний отбой: {self._on(settings.bedtime_reminder_enabled)}\n"
      f"Check-in утром: {self._on(settings.wake_checkin_enabled)}\n"
      f"Дневное восстановление: {self._on(settings.day_recovery_enabled)}\n"
      f"Фокус-перерыв: {self._on(settings.focus_reminder_enabled)}\n"
      f"Время вечернего напоминания: {settings.reminder_time}\n\n"
      "Эти настройки управляют тем, какие напоминания бот будет предлагать и сохранять. "
      "Бот не будет присылать маркетинг без отдельного согласия."
    )

  def quick_repeat_text(self, user_id: UUID) -> str:
    recommendations = self._recommendations(user_id)
    if not recommendations:
      return (
        "🔁 Повторить последнее\n\n"
        "Пока нет сохранённого сценария. Сначала пройди любой сценарий: ночной сон, power nap, "
        "медитацию или технику пробуждения."
      )
    recommendation = recommendations[-1]
    lines = [
      "🔁 Повторяю последний сценарий",
      "",
      f"Сценарий: {recommendation.recommended_mode.value}",
      f"Длительность: {recommendation.duration_minutes} мин",
      f"Аудио: {recommendation.audio.value}",
      "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(recommendation.steps, 1))
    lines.append("")
    lines.append("После выполнения можешь нажать «✅ Я проснулся» или пройти check-in.")
    return "\n".join(lines)

  def concentration_text(self, minutes: int) -> str:
    if minutes <= 5:
      steps = (
        "Убери телефонные уведомления на 5 минут.",
        "Сделай 5 спокойных выдохов длиннее вдоха.",
        "Выбери одну маленькую задачу и начни с первого действия.",
      )
      title = "быстрый reset фокуса"
    elif minutes <= 10:
      steps = (
        "Закрой лишние вкладки и оставь один источник задачи.",
        "2 минуты спокойно подыши и расслабь плечи.",
        "8 минут работай только над одним действием без переключений.",
      )
      title = "короткое восстановление концентрации"
    else:
      steps = (
        "5 минут разгрузи голову: выпиши всё, что мешает.",
        "5 минут спокойно подыши и убери напряжение в плечах.",
        "Оставшееся время работай над одной задачей в мягком темпе.",
      )
      title = "расширенный focus recovery"
    lines = [
      "🎯 Практика концентрации",
      "",
      f"Формат: {title}",
      f"Длительность: {minutes} мин",
      "",
    ]
    lines.extend(f"{index}. {step}" for index, step in enumerate(steps, 1))
    lines.extend(
      [
        "",
        "Это не лечение усталости, а короткий способ снизить шум и вернуться к задаче.",
      ]
    )
    return "\n".join(lines)

  def period_stats_text(self, user_id: UUID, days: int) -> str:
    entries = self._entries(user_id)[-days:]
    recommendations = self._recommendations(user_id)[-days * 3:]
    if not entries and not recommendations:
      return f"📆 Статистика за {days} дней\n\nПока мало данных. Пройди check-in после сна 2-3 раза."
    avg_sleep = self._avg([entry.duration_minutes for entry in entries])
    avg_quality = self._avg([entry.quality for entry in entries])
    avg_feeling = self._avg([entry.post_wake_feeling for entry in entries])
    debt = self._sleep_debt(entries, target=480)
    modes = self._top_modes(recommendations)
    return (
      f"📆 Статистика за {days} дней\n\n"
      f"Check-in записей: {len(entries)}\n"
      f"Сценариев: {len(recommendations)}\n"
      f"Средняя длительность сна: {self._minutes(avg_sleep)}\n"
      f"Среднее качество сна: {self._score(avg_quality)}\n"
      f"Самочувствие после сна: {self._score(avg_feeling)}\n"
      f"Оценочный долг сна: {debt} мин\n"
      f"Частые сценарии: {modes}\n\n"
      "Вывод: статистика основана на субъективных check-in и не является медицинской диагностикой."
    )

  def scenario_comparison_text(self, user_id: UUID) -> str:
    recommendations = self._recommendations(user_id)
    feedback = self.store.recommendation_feedback.get(user_id, [])
    if not recommendations:
      return "⚖️ Сравнение сценариев\n\nПока нет сценариев для сравнения."
    rec_by_id = {item.id: item for item in recommendations}
    scores: dict[str, list[int]] = {}
    for item in feedback:
      recommendation = rec_by_id.get(item.recommendation_id)
      if recommendation is None:
        continue
      scores.setdefault(recommendation.recommended_mode.value, []).append(item.helpfulness)
    counts: dict[str, int] = {}
    for recommendation in recommendations:
      mode = recommendation.recommended_mode.value
      counts[mode] = counts.get(mode, 0) + 1
    lines = ["⚖️ Сравнение сценариев", ""]
    for mode, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]:
      values = scores.get(mode, [])
      avg = "нет оценок" if not values else f"{sum(values) / len(values):.1f}/5"
      lines.append(f"- {mode}: запусков {count}, средняя полезность {avg}")
    lines.extend(
      [
        "",
        "Как читать: сценарий с высокой полезностью и несколькими повторами можно считать более подходящим.",
      ]
    )
    return "\n".join(lines)

  def release2_status_text(self, user_id: UUID) -> str:
    return (
      "✅ Release 2 включён\n\n"
      "Доступно в боте:\n"
      "- настройки уведомлений и напоминаний\n"
      "- практики концентрации\n"
      "- быстрый повтор последнего сценария\n"
      "- техники быстрого засыпания и пробуждения\n"
      "- power nap и дневное восстановление\n"
      "- статистика за 7 / 30 дней\n"
      "- сравнение сценариев по истории и оценкам\n\n"
      f"Текущие напоминания:\n{self.reminders_text(user_id)}"
    )

  def _entries(self, user_id: UUID) -> list[SleepEntry]:
    return list(self.store.entries.get(user_id, []))

  def _recommendations(self, user_id: UUID) -> list[Recommendation]:
    return list(self.store.recommendations.get(user_id, []))

  def _ensure_schema(self) -> None:
    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    with self._connect() as connection:
      connection.execute(
        """
        CREATE TABLE IF NOT EXISTS release2_reminder_settings (
          user_id TEXT PRIMARY KEY,
          notifications_enabled INTEGER NOT NULL,
          bedtime_reminder_enabled INTEGER NOT NULL,
          wake_checkin_enabled INTEGER NOT NULL,
          day_recovery_enabled INTEGER NOT NULL,
          focus_reminder_enabled INTEGER NOT NULL,
          reminder_time TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
      )

  def _connect(self) -> sqlite3.Connection:
    connection = sqlite3.connect(self.db_path)
    connection.row_factory = sqlite3.Row
    return connection

  def _avg(self, values: list[int]) -> float | None:
    return None if not values else sum(values) / len(values)

  def _minutes(self, value: float | None) -> str:
    if value is None:
      return "нет данных"
    hours = int(value) // 60
    minutes = int(value) % 60
    if minutes == 0:
      return f"{hours} ч"
    if minutes == 30:
      return f"{hours}.5 ч"
    return f"{hours} ч {minutes:02d} мин"

  def _score(self, value: float | None) -> str:
    return "нет данных" if value is None else f"{value:.1f}/5"

  def _sleep_debt(self, entries: list[SleepEntry], target: int) -> int:
    return max(0, sum(max(0, target - entry.duration_minutes) for entry in entries))

  def _top_modes(self, recommendations: list[Recommendation]) -> str:
    if not recommendations:
      return "нет данных"
    counts: dict[str, int] = {}
    for recommendation in recommendations:
      mode = recommendation.recommended_mode.value
      counts[mode] = counts.get(mode, 0) + 1
    top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:3]
    return ", ".join(f"{mode} ({count})" for mode, count in top)

  def _on(self, value: bool) -> str:
    return "вкл" if value else "выкл"
