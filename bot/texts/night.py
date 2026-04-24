from app.schemas import RecommendationOutput
from bot.texts.common import render_recommendation

INTRO_TEXT = (
    "Соберу короткий вечерний сценарий под ваше состояние. "
    "Сначала несколько вопросов без оценки и без давления."
)


def render_night_recommendation(recommendation: RecommendationOutput) -> str:
    return render_recommendation("Ночной сценарий", recommendation)
