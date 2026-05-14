from __future__ import annotations

from packages.billing.providers import MockBillingProvider
from packages.billing.service import BillingService
from packages.domain.models import new_uuid


def test_mock_payment_creates_subscription_and_entitlements() -> None:
    user_id = new_uuid()
    billing = BillingService(MockBillingProvider())

    intent = billing.create_checkout(user_id, "premium_monthly", "checkout-1")
    subscription = billing.confirm_mock_payment(intent.idempotency_key)

    assert subscription.user_id == user_id
    assert billing.has_feature(user_id, "advanced_analytics")


def test_checkout_idempotency() -> None:
    user_id = new_uuid()
    billing = BillingService(MockBillingProvider())

    first = billing.create_checkout(user_id, "premium_monthly", "same")
    second = billing.create_checkout(user_id, "premium_monthly", "same")

    assert first.id == second.id
