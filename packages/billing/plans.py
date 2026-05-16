from __future__ import annotations

from packages.domain.models import SubscriptionPlan

FREE_FEATURES = frozenset({
    "basic_flows",
    "basic_history",
    "basic_stats",
    "limited_content",
})

PREMIUM_FEATURES = frozenset({
    *FREE_FEATURES,
    "advanced_flows",
    "advanced_analytics",
    "weekly_insights",
    "content_packs",
    "smart_personalization",
    "richer_audio_library",
    "custom_routines",
    "deep_history",
    "experiments",
})

PLANS = {
    "premium_monthly": SubscriptionPlan(
        code="premium_monthly",
        title="Sleep Support Premium 30 дней",
        price_minor=299,
        currency="XTR",
        period_days=30,
        trial_days=0,
        features=PREMIUM_FEATURES,
    ),
    "premium_yearly": SubscriptionPlan(
        code="premium_yearly",
        title="Sleep Support Premium 365 дней",
        price_minor=2490,
        currency="XTR",
        period_days=365,
        trial_days=0,
        features=PREMIUM_FEATURES,
    ),
}


def get_plan(code: str) -> SubscriptionPlan:
    try:
        return PLANS[code]
    except KeyError as exc:
        raise ValueError(f"unknown plan: {code}") from exc