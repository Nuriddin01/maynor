from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from packages.domain.models import BillingProviderName, PaymentIntent, new_uuid


@dataclass(frozen=True)
class CheckoutRequest:
    user_id: UUID
    plan_code: str
    amount_minor: int
    currency: str
    idempotency_key: str


class BillingProvider(Protocol):
    name: BillingProviderName
    def create_checkout(self, request: CheckoutRequest, now: datetime) -> PaymentIntent: ...
    def parse_webhook(self, payload: dict[str, object]) -> dict[str, object]: ...


class MockBillingProvider:
    name = BillingProviderName.MOCK

    def create_checkout(self, request: CheckoutRequest, now: datetime) -> PaymentIntent:
        return PaymentIntent(
            id=new_uuid(),
            user_id=request.user_id,
            plan_code=request.plan_code,
            provider=self.name,
            amount_minor=request.amount_minor,
            currency=request.currency,
            status="requires_confirmation",
            payment_url=f"http://localhost:8000/admin/payments/mock/confirm/{request.idempotency_key}",
            idempotency_key=request.idempotency_key,
            created_at=now,
        )

    def parse_webhook(self, payload: dict[str, object]) -> dict[str, object]:
        if "idempotency_key" not in payload:
            raise ValueError("idempotency_key is required")
        return {"status": payload.get("status", "paid"), "idempotency_key": payload["idempotency_key"]}


class TelegramStarsBillingProvider:
    name = BillingProviderName.TELEGRAM_STARS

    def create_checkout(self, request: CheckoutRequest, now: datetime) -> PaymentIntent:
        return PaymentIntent(
            id=new_uuid(),
            user_id=request.user_id,
            plan_code=request.plan_code,
            provider=self.name,
            amount_minor=request.amount_minor,
            currency=request.currency,
            status="provider_configuration_required",
            payment_url="telegram-stars://invoice-created-by-bot-adapter",
            idempotency_key=request.idempotency_key,
            created_at=now,
        )

    def parse_webhook(self, payload: dict[str, object]) -> dict[str, object]:
        if "telegram_payment_charge_id" not in payload:
            raise ValueError("telegram_payment_charge_id is required")
        return {"status": "paid", "telegram_payment_charge_id": payload["telegram_payment_charge_id"]}
