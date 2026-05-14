from __future__ import annotations

from packages.domain.models import Recommendation

MAIN_MENU = "Выбери, что сейчас нужно:"
CONSENT_TEXT = (
    "Перед началом нужно согласие на базовую обработку данных сна и настроек. "
    "Мы используем минимум данных, не ставим диагнозы и не заменяем врача."
)
DISCLAIMER = "Бот не заменяет врача. Если проблемы со сном стали постоянными или сильно мешают жизни, обратитесь к специалисту."


def recommendation_text(recommendation: Recommendation) -> str:
    steps = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(recommendation.steps))
    parts = [
        f"Режим: {recommendation.recommended_mode.value}",
        f"Длительность: {recommendation.duration_minutes} мин",
        f"Аудио: {recommendation.audio.value}",
    ]
    if recommendation.snapshot.get("sleep_debt_minutes") is not None:
        parts.append(f"Долг сна: {recommendation.snapshot['sleep_debt_minutes']} мин")
    if recommendation.snapshot.get("recommended_bedtime"):
        parts.append(f"Рекомендуемый отбой: {recommendation.snapshot['recommended_bedtime']}")
    if recommendation.snapshot.get("target_wake_time"):
        parts.append(f"Подъём: {recommendation.snapshot['target_wake_time']}")
    if recommendation.snapshot.get("baseline_used"):
        parts.append("Данных пока мало, поэтому использую базовый ориентир.")
    if recommendation.snapshot.get("reminder_offer"):
        parts.append("Можно включить напоминание перед выполнением рекомендации.")
    if recommendation.snapshot.get("feedback_prompt"):
        parts.append(str(recommendation.snapshot["feedback_prompt"]))
    return "\n".join(parts) + f"\n\n{steps}\n\n{recommendation.disclaimer}"
