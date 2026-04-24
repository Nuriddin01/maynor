from __future__ import annotations

from app.constants import DISCLAIMER_TEXT, MODE_DISPLAY_NAMES
from app.schemas import RecommendationOutput, StatsSummary
from app.utils.time_utils import format_datetime_for_user, format_minutes

MENU_READY_TEXT = "Готово. Возвращаю вас в главное меню."


def build_welcome_text(name: str | None) -> str:
    intro = "Sleep Support Bot — wellbeing-сервис для мягкой поддержки сна и восстановления."
    base = (
        f"{intro}\n\n"
        "Что умеет:\n"
        "• вечерние и дневные сценарии\n"
        "• отдельный режим Power Nap\n"
        "• check-in после сна\n"
        "• история, статистика и будильник с кодом\n\n"
        f"{DISCLAIMER_TEXT}"
    )
    return f"Привет, {name}.\n\n{base}" if name else f"Привет.\n\n{base}"


HELP_TEXT = (
    "Команды: /start /night /day /power_nap /wake /history /stats /alarm /settings /premium /help\n\n"
    "Старайтесь отвечать цифрами в указанном диапазоне. В любом сценарии можно нажать «Назад» или «В меню».\n\n"
    f"{DISCLAIMER_TEXT}"
)


def render_recommendation(title: str, recommendation: RecommendationOutput) -> str:
    steps = "\n".join(f"• {step}" for step in recommendation.recommended_steps)
    return (
        f"{title}\n\n"
        f"Режим: {MODE_DISPLAY_NAMES.get(recommendation.recommended_mode, recommendation.recommended_mode)}\n"
        f"Длительность: {recommendation.recommended_duration_minutes or 'гибко'} мин\n"
        f"Уверенность: {recommendation.confidence_label}\n"
        f"Аудио: {recommendation.optional_audio_type or 'по желанию'}\n\n"
        f"{recommendation.explanation_for_user}\n\n"
        f"Шаги:\n{steps}\n\n"
        f"Дальше: {recommendation.followup_hint}\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def render_history(entries: list) -> str:
    if not entries:
        return "История пока пустая."
    lines = ["Последние записи:"]
    for entry in entries:
        lines.append(
            f"• {entry.created_at:%d.%m %H:%M} | {MODE_DISPLAY_NAMES.get(entry.mode, entry.mode)} | "
            f"{format_minutes(entry.duration_minutes)} | качество: {entry.subjective_sleep_quality_1_5 or '—'} | "
            f"после пробуждения: {entry.felt_after_waking_1_5 or '—'}"
        )
        if entry.notes:
            lines.append(f"  заметка: {entry.notes}")
    return "\n".join(lines)


def render_stats(summary: StatsSummary) -> str:
    if summary.entries_count_last_30_days == 0:
        return "Данных пока нет."
    insights = "\n".join(f"• {item}" for item in summary.pattern_insights)
    return (
        "Статистика:\n\n"
        f"Средняя длительность за 7 дней: {summary.average_duration_minutes_last_7_days or '—'} мин\n"
        f"Средняя длительность за 30 дней: {summary.average_duration_minutes_last_30_days or '—'} мин\n"
        f"Среднее качество сна: {summary.average_sleep_quality_last_30_days or '—'}\n"
        f"Среднее состояние после пробуждения: {summary.average_felt_after_last_30_days or '—'}\n"
        f"Частые режимы: {', '.join(summary.most_used_modes) or '—'}\n"
        f"Полезные режимы: {', '.join(summary.most_helpful_modes) or '—'}\n\n"
        f"Выводы:\n{insights}\n\n{DISCLAIMER_TEXT}"
    )


def render_settings(overview: dict) -> str:
    return (
        "Настройки:\n\n"
        f"• Таймзона: {overview['timezone']}\n"
        f"• Язык: {overview['language']}\n"
        f"• Аудио: {overview['preferred_audio']}\n"
        f"• dislike white noise: {'да' if overview['dislikes_white_noise'] else 'нет'}\n"
        f"• default nap: {overview['default_nap_minutes'] or 'не задан'}\n"
        f"• reminders: {'вкл' if overview['reminders_enabled'] else 'выкл'}\n"
        f"• Формат времени: {overview['time_format']}\n"
        f"• Premium: {'активен' if overview['premium_status'] else 'не активен'}"
    )


def render_alarm_created(alarm_time, timezone_name: str, time_format: str, code: str) -> str:
    return (
        "Будильник установлен.\n"
        f"Время: {format_datetime_for_user(alarm_time, timezone_name, time_format)}\n"
        f"Код остановки: {code}\n"
        "Для выключения отправьте: /stop_alarm КОД"
    )
