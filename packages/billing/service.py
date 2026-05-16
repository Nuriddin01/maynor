from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from packages.billing.plans import FREE_FEATURES, get_plan
from packages.billing.providers import BillingProvider, CheckoutRequest
from packages.domain.models import BillingProviderName, PaymentIntent, Subscription, SubscriptionStatus, new_uuid


class BillingStore(Protocol):
    def get_payment(self, idempotency_key: str) -> PaymentIntent | None: ...
    def save_payment(self, intent: PaymentIntent) -> PaymentIntent: ...
    def get_subscription(self, user_id: UUID) -> Subscription | None: ...
    def save_subscription(self, subscription: Subscription) -> Subscription: ...


@dataclass
class BillingMemoryStore:
    subscriptions: dict[UUID, Subscription]
    payments: dict[str, PaymentIntent]

    @classmethod
    def empty(cls) -> BillingMemoryStore:
        return cls(subscriptions={}, payments={})

    def get_payment(self, idempotency_key: str) -> PaymentIntent | None:
        return self.payments.get(idempotency_key)

    def save_payment(self, intent: PaymentIntent) -> PaymentIntent:
        self.payments[intent.idempotency_key] = intent
        return intent

    def get_subscription(self, user_id: UUID) -> Subscription | None:
        return self.subscriptions.get(user_id)

    def save_subscription(self, subscription: Subscription) -> Subscription:
        self.subscriptions[subscription.user_id] = subscription
        return subscription


class BillingService:
    def __init__(self, provider: BillingProvider, store: BillingStore | None = None) -> None:
        self._provider = provider
        self._store = store or BillingMemoryStore.empty()

    def create_checkout(self, user_id: UUID, plan_code: str, idempotency_key: str, now: datetime | None = None) -> PaymentIntent:
        now = now or datetime.now(timezone.utc)
        existing = self._store.get_payment(idempotency_key)
        if existing:
            return existing
        plan = get_plan(plan_code)
        intent = self._provider.create_checkout(
            CheckoutRequest(
                user_id=user_id,
                plan_code=plan.code,
                amount_minor=plan.price_minor,
                currency=plan.currency,
                idempotency_key=idempotency_key,
            ),
            now,
        )
        return self._store.save_payment(intent)

    def confirm_mock_payment(self, idempotency_key: str, now: datetime | None = None) -> Subscription:
        now = now or datetime.now(timezone.utc)
        intent = self._store.get_payment(idempotency_key)
        if intent is None:
            raise KeyError("payment intent not found")
        plan = get_plan(intent.plan_code)
        status = SubscriptionStatus.TRIALING if plan.trial_days > 0 else SubscriptionStatus.ACTIVE
        period_days = plan.trial_days or plan.period_days
        subscription = Subscription(
            id=new_uuid(),
            user_id=intent.user_id,
            plan_code=plan.code,
            status=status,
            provider=BillingProviderName.MOCK,
            current_period_end=now + timedelta(days=period_days),
            created_at=now,
        )
        return self._store.save_subscription(subscription)

    def confirm_telegram_stars_payment(
        self,
        user_id: UUID,
        plan_code: str,
        idempotency_key: str,
        amount_minor: int,
        currency: str,
        telegram_payment_charge_id: str,
        now: datetime | None = None,
    ) -> Subscription:
        now = now or datetime.now(timezone.utc)
        plan = get_plan(plan_code)
        if currency != "XTR":
            raise ValueError("Telegram Stars payment must use XTR currency")
        if amount_minor != plan.price_minor:
            raise ValueError("payment amount does not match selected plan")

        existing = self._store.get_payment(idempotency_key)
        if existing is None:
            intent = PaymentIntent(
                id=new_uuid(),
                user_id=user_id,
                plan_code=plan.code,
                provider=BillingProviderName.TELEGRAM_STARS,
                amount_minor=amount_minor,
                currency=currency,
                status="paid",
                payment_url=f"telegram-stars://{telegram_payment_charge_id}",
                idempotency_key=idempotency_key,
                created_at=now,
            )
        else:
            intent = PaymentIntent(
                id=existing.id,
                user_id=existing.user_id,
                plan_code=existing.plan_code,
                provider=BillingProviderName.TELEGRAM_STARS,
                amount_minor=amount_minor,
                currency=currency,
                status="paid",
                payment_url=f"telegram-stars://{telegram_payment_charge_id}",
                idempotency_key=existing.idempotency_key,
                created_at=existing.created_at,
            )
        self._store.save_payment(intent)

        subscription = Subscription(
            id=new_uuid(),
            user_id=user_id,
            plan_code=plan.code,
            status=SubscriptionStatus.ACTIVE,
            provider=BillingProviderName.TELEGRAM_STARS,
            current_period_end=now + timedelta(days=plan.period_days),
            created_at=now,
        )
        return self._store.save_subscription(subscription)

    def cancel(self, user_id: UUID, now: datetime | None = None) -> Subscription:
        now = now or datetime.now(timezone.utc)
        subscription = self._store.get_subscription(user_id)
        if subscription is None:
            raise KeyError("subscription not found")
        canceled = Subscription(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_code=subscription.plan_code,
            status=SubscriptionStatus.CANCELED,
            provider=subscription.provider,
            current_period_end=subscription.current_period_end,
            created_at=subscription.created_at,
            canceled_at=now,
        )
        return self._store.save_subscription(canceled)

    def active_features(self, user_id: UUID, now: datetime | None = None) -> frozenset[str]:
        now = now or datetime.now(timezone.utc)
        subscription = self._store.get_subscription(user_id)
        if subscription is None:
            return FREE_FEATURES
        if subscription.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.GRACE} and subscription.current_period_end >= now:
            return get_plan(subscription.plan_code).features
        return FREE_FEATURES

    def has_feature(self, user_id: UUID, feature: str, now: datetime | None = None) -> bool:
        return feature in self.active_features(user_id, now)
