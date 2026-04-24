from app.schemas import RecommendationOutput
from bot.texts.common import render_recommendation

INTRO_TEXT = (
    "Подберу формат дневного отдыха: короткий перерыв, попытку nap или более длинную сессию."
)


def render_day_recommendation(recommendation: RecommendationOutput) -> str:
    return render_recommendation("Дневной отдых", recommendation)
