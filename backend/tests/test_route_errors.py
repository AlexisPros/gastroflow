from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import kitchen_task as crud_kitchen_task
from app.crud import order as crud_order
from app.crud import payment as crud_payment
from app.main import app
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.services import discount_service, payment_service


client = TestClient(app)


def make_user(role: str) -> User:
    return User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash="hash",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def make_order() -> Order:
    return Order(
        id=1,
        table_id=1,
        waiter_id=1,
        discount_id=None,
        shift_id=None,
        source="WAITER",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("25.00"),
        subtotal_amount=Decimal("25.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
    )


def make_payment() -> Payment:
    return Payment(
        id=1,
        order_id=1,
        method="CARD",
        amount=Decimal("25.00"),
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )


def make_kitchen_task() -> KitchenTask:
    return KitchenTask(
        id=1,
        order_item_id=1,
        kitchen_section_id=1,
        assigned_user_id=None,
        status="NEW",
        estimated_time=10,
        started_at=None,
        completed_at=None,
    )


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def test_protected_route_without_token_returns_401():
    response = client.get("/api/v1/restaurant-tables")

    assert response.status_code == 401


def test_wrong_role_returns_403_before_business_logic():
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/stock-items/1/movements/apply",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "type": "DELIVERY",
                "quantity_delta": "5.00",
                "description": "Test",
                "prevent_negative": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_missing_resource_returns_404(monkeypatch):
    async def get(_db, id: int):
        assert id == 999
        return None

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/999/start",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "kitchen task not found."


def test_service_value_error_returns_400(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def apply_discount(_db, *, order, discount_id: int):
        assert order.id == 1
        assert discount_id == 999
        raise ValueError("Discount does not exist.")

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(discount_service, "apply_discount", apply_discount)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/orders/1/discount",
            headers={"Authorization": "Bearer fake-token"},
            json={"discount_id": 999},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Discount does not exist."


def test_payment_value_error_returns_400(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_payment()

    async def cancel_payment(_db, *, payment):
        assert payment.id == 1
        raise ValueError("Refunded payment cannot be cancelled.")

    monkeypatch.setattr(crud_payment, "get", get)
    monkeypatch.setattr(payment_service, "cancel_payment", cancel_payment)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/payments/1/cancel",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Refunded payment cannot be cancelled."
