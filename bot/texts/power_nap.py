from app.schemas import RecommendationOutput
from bot.texts.common import render_recommendation

INTRO_TEXT = (
    "Этот режим нужен для быстрых 10-20 минут восстановления, когда окно времени уже более-менее понятно."
)


def render_power_nap_recommendation(recommendation: RecommendationOutput) -> str:
    return render_recommendation("Power Nap", recommendation)
