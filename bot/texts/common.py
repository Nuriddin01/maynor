from __future__ import annotations

from app.constants import DISCLAIMER_TEXT, MODE_DISPLAY_NAMES
from app.schemas import RecommendationOutput, StatsSummary
from app.utils.time_utils import format_datetime_for_user, format_minutes

MENU_READY_TEXT = "Готово. Возвращаю вас в главное меню."

WELCOME_TEXT = (
    "Sleep Support Bot помогает мягко подготовиться ко сну, сделать короткий дневной отдых, "
    "поставить будильник и отслеживать, что реально помогает именно вам.\n\n"
    "Я не ставлю диагнозы и не обещаю лечение. Здесь только бережные, понятные и безопасные рекомендации.\n\n"
    f"{DISCLAIMER_TEXT}"
)

HELP_TEXT = (
    "Что умеет бот:\n"
    "• подсказывает вечерний сценарий для засыпания\n"
    "• помогает с дневным отдыхом и power nap\n"
    "• сохраняет check-in после сна\n"
    "• показывает историю и простую статистику\n"
    "• ставит будильники внутри Telegram с кодом остановки\n"
    "• хранит базовые настройки аудио, языка и часового пояса\n\n"
    "Как пользоваться:\n"
    "1. Выберите режим в главном меню.\n"
    "2. Ответьте на короткие вопросы.\n"
    "3. Получите сценарий и при необходимости будильник.\n"
    "4. После сна заполните check-in, чтобы улучшить персонализацию.\n\n"
    f"{DISCLAIMER_TEXT}"
)


def build_welcome_text(name: str | None) -> str:
    if name:
        return f"Привет, {name}.\n\n{WELCOME_TEXT}"
    return f"Привет.\n\n{WELCOME_TEXT}"


def render_recommendation(title: str, recommendation: RecommendationOutput) -> str:
    steps = "\n".join(f"• {step}" for step in recommendation.steps)
    audio_line = recommendation.optional_audio_type or "не обязательно"
    duration_line = (
        f"{recommendation.recommended_duration_minutes} мин"
        if recommendation.recommended_duration_minutes is not None
        else "без жесткой длительности"
    )
    return (
        f"{title}\n\n"
        f"Режим: {MODE_DISPLAY_NAMES.get(recommendation.recommended_mode, recommendation.recommended_mode)}\n"
        f"Рекомендуемое окно: {duration_line}\n"
        f"Уверенность: {recommendation.confidence_label}\n\n"
        f"{recommendation.explanation_for_user}\n\n"
        "Шаги:\n"
        f"{steps}\n\n"
        f"Дыхательная практика: {recommendation.breathing_practice}\n"
        f"Расслабление: {recommendation.relaxation_tip}\n"
        f"Sleep hygiene: {recommendation.sleep_hygiene_tip}\n"
        f"Аудио: {audio_line}\n"
        f"Дальше: {recommendation.followup_hint}\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def render_history(entries: list) -> str:
    if not entries:
        return (
            "История пока пустая. Начните с любого сценария и сохраните check-in после сна, "
            "чтобы здесь появились записи."
        )

    lines = ["Последние записи:\n"]
    for entry in entries:
        lines.append(
            (
                f"• {entry.created_at.strftime('%d.%m %H:%M')} | "
                f"{MODE_DISPLAY_NAMES.get(entry.mode, entry.mode)} | "
                f"{format_minutes(entry.duration_minutes)} | "
                f"качество: {entry.subjective_sleep_quality_1_5 or '—'} | "
                f"самочувствие: {entry.felt_after_waking_1_5 or '—'}"
            )
        )
    lines.append(f"\n{DISCLAIMER_TEXT}")
    return "\n".join(lines)


def render_stats(summary: StatsSummary) -> str:
    if summary.entries_count_last_7_days == 0:
        return summary.pattern_insights[0]

    used_modes = ", ".join(summary.most_used_modes) if summary.most_used_modes else "пока нет"
    helpful_modes = ", ".join(summary.most_helpful_modes) if summary.most_helpful_modes else "пока нет"
    insights = "\n".join(f"• {insight}" for insight in summary.pattern_insights)
    return (
        "Статистика за последние 7 дней:\n\n"
        f"Средняя длительность: {format_minutes(int(summary.average_duration_minutes_last_7_days or 0))}\n"
        f"Среднее качество сна: {summary.average_sleep_quality_last_7_days or '—'}\n"
        f"Среднее самочувствие после пробуждения: {summary.average_felt_after_last_7_days or '—'}\n"
        f"Самые частые режимы: {used_modes}\n"
        f"Самые полезные режимы: {helpful_modes}\n\n"
        "Наблюдения:\n"
        f"{insights}\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def render_settings(overview: dict) -> str:
    return (
        "Текущие настройки:\n\n"
        f"Часовой пояс: {overview['timezone']}\n"
        f"Язык профиля: {overview['language']}\n"
        f"Предпочитаемое аудио: {overview['preferred_audio']}\n"
        f"Формат времени: {overview['time_format']}\n"
        f"Sleep hygiene советы: {'вкл' if overview['sleep_hygiene_tips'] else 'выкл'}\n"
        f"Аудио-рекомендации: {'вкл' if overview['audio_recommendations'] else 'выкл'}\n"
        f"Premium: {'активен' if overview['premium_status'] else 'не активен'}\n\n"
        "Выберите, что хотите изменить."
    )


def render_alarm_created(alarm_time, timezone_name: str, time_format: str, code: str) -> str:
    return (
        "Будильник установлен.\n\n"
        f"Когда сработает: {format_datetime_for_user(alarm_time, timezone_name, time_format)}\n"
        f"Код остановки: {code}\n"
        "Когда будильник сработает, я попрошу ввести этот код в чат.\n\n"
        f"{DISCLAIMER_TEXT}"
    )
