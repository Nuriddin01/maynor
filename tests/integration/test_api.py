from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import create_app


def test_health_and_recommendation_flow() -> None:
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    client.post("/users/start", json={"telegram_id": 100, "username": "test"})
    client.post("/users/100/consents/accept-required")
    response = client.post(
        "/recommendations/night",
        json={
            "telegram_id": 100,
            "slept_last_night_minutes": 420,
            "quality": 3,
            "sleepiness": 4,
            "stress": 5,
            "free_minutes": 15,
            "needs_alarm": False,
            "preferred_audio": "rain",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_mode"] == "stress_down_protocol"


def test_admin_requires_token() -> None:
    client = TestClient(create_app())

    assert client.get("/admin/users").status_code == 401
    assert client.get("/admin/users", headers={"X-Admin-Token": "change-me-local-admin-token"}).status_code == 200


def test_billing_mock_flow() -> None:
    client = TestClient(create_app())
    client.post("/users/start", json={"telegram_id": 200})

    checkout = client.post(
        "/billing/checkout",
        json={"telegram_id": 200, "plan_code": "premium_monthly", "idempotency_key": "pay-200"},
    )
    assert checkout.status_code == 200
    confirm = client.post("/billing/mock/confirm/pay-200")
    assert confirm.status_code == 200
    assert confirm.json()["plan_code"] == "premium_monthly"
