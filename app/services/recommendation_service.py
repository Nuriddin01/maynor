from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.recommendation_engine import RecommendationEngine
from app.schemas import RecommendationOutput, RecommendationRequest
from app.services.sleep_service import SleepService
from app.services.user_service import UserService


class RecommendationService:
    def __init__(
        self,
        engine: RecommendationEngine,
        sleep_service: SleepService,
        user_service: UserService,
    ) -> None:
        self.engine = engine
        self.sleep_service = sleep_service
        self.user_service = user_service

    async def build_for_user(
        self,
        session: AsyncSession,
        user: User,
        payload: RecommendationRequest,
    ) -> RecommendationOutput:
        history = await self.sleep_service.get_history_for_recommendation(session, user.id, days=7)
        preference = await self.user_service.ensure_preferences(session, user)

        enriched_payload = payload.model_copy(
            update={
                "history": history,
                "preferred_audio": preference.preferred_audio,
                "dislikes_white_noise": preference.dislikes_white_noise,
                "likes_rain": preference.likes_rain,
                "likes_forest": preference.likes_forest,
                "likes_silence": preference.likes_silence,
            }
        )
        recommendation = self.engine.build_recommendation(enriched_payload)
        if not preference.enable_audio_recommendations:
            recommendation = recommendation.model_copy(update={"optional_audio_type": None})
        if not preference.enable_sleep_hygiene_tips:
            recommendation = recommendation.model_copy(update={"sleep_hygiene_tip": "Совет по гигиене сна отключен в настройках."})
        return recommendation
