from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import order as crud_order
from app.crud import restaurant_table as crud_restaurant_table
from app.main import app
from app.models.order import Order
from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.services import order_service, user_service


client = TestClient(app)


def make_user(role: str = "WAITER") -> User:
    return User(
        id=7,
        first_name="Test",
        last_name="Waiter",
        email="waiter@example.com",
        password_hash="hash",
        pin_hash="pin-hash",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(role: str = "WAITER") -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def make_restaurant_table() -> RestaurantTable:
    return RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="FREE",
        qr_code_url="http://localhost:3000/qr/a1-token",
        qr_token="a1-token",
        is_active=True,
    )


def make_pending_qr_order() -> Order:
    return Order(
        id=1,
        version=1,
        table_id=1,
        waiter_id=None,
        discount_id=None,
        shift_id=None,
        guest_count=2,
        source="QR",
        status="PENDING_CONFIRMATION",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("42.00"),
        subtotal_amount=Decimal("42.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
        estimated_time=None,
    )


def make_confirmed_qr_order() -> Order:
    order = make_pending_qr_order()
    order.waiter_id = 7
    order.status = "OPEN"
    order.estimated_time = 15
    return order


def make_rejected_qr_order() -> Order:
    order = make_pending_qr_order()
    order.waiter_id = 7
    order.status = "REJECTED"
    return order


def test_get_qr_table_is_public(monkeypatch):
    async def get_by_qr_token(_db, *, qr_token: str):
        assert qr_token == "a1-token"
        return make_restaurant_table()

    monkeypatch.setattr(
        crud_restaurant_table,
        "get_by_qr_token",
        get_by_qr_token,
    )

    response = client.get("/api/v1/qr/a1-token/table")

    assert response.status_code == 200
    assert response.json()["table_number"] == "A1"
    assert response.json()["qr_code_url"] == "http://localhost:3000/qr/a1-token"


def test_get_qr_table_returns_404_for_unknown_token(monkeypatch):
    async def get_by_qr_token(_db, *, qr_token: str):
        assert qr_token == "missing-token"
        return None

    monkeypatch.setattr(
        crud_restaurant_table,
        "get_by_qr_token",
        get_by_qr_token,
    )

    response = client.get("/api/v1/qr/missing-token/table")

    assert response.status_code == 404
    assert response.json()["detail"] == "QR table not found."


def test_create_qr_pending_order_reaches_service(monkeypatch):
    async def get_by_qr_token(_db, *, qr_token: str):
        assert qr_token == "a1-token"
        return make_restaurant_table()

    async def create_pending_qr_order(
        _db,
        *,
        table_id: int,
        guest_count: int,
        items,
    ):
        assert table_id == 1
        assert guest_count == 2
        assert len(items) == 1
        assert items[0].product_id == 10
        assert items[0].quantity == 2
        assert items[0].notes == "No onion"
        assert items[0].product_modifier_ids == [3]
        return make_pending_qr_order()

    monkeypatch.setattr(
        crud_restaurant_table,
        "get_by_qr_token",
        get_by_qr_token,
    )
    monkeypatch.setattr(
        order_service,
        "create_pending_qr_order",
        create_pending_qr_order,
    )

    response = client.post(
        "/api/v1/qr/a1-token/orders",
        json={
            "guest_count": 2,
            "items": [
                {
                    "product_id": 10,
                    "quantity": 2,
                    "notes": "No onion",
                    "product_modifier_ids": [3],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["source"] == "QR"
    assert response.json()["status"] == "PENDING_CONFIRMATION"
    assert response.json()["waiter_id"] is None
    assert response.json()["guest_count"] == 2


def test_create_qr_pending_order_validates_guest_count():
    response = client.post(
        "/api/v1/qr/a1-token/orders",
        json={
            "guest_count": 0,
            "items": [
                {
                    "product_id": 10,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 422


def test_list_pending_qr_orders_requires_order_role(monkeypatch):
    async def get_pending_qr_orders(_db, *, skip: int, limit: int):
        assert skip == 0
        assert limit == 100
        return [make_pending_qr_order()]

    monkeypatch.setattr(
        crud_order,
        "get_pending_qr_orders",
        get_pending_qr_orders,
    )
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/qr/orders/pending",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["status"] == "PENDING_CONFIRMATION"


def test_confirm_qr_pending_order_uses_pin_user(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_pending_qr_order()

    async def find_service_order_user_by_pin(_db, *, pin: str):
        assert pin == "1234"
        return make_user("WAITER")

    async def confirm_pending_qr_order(_db, *, order, waiter_id: int):
        assert order.id == 1
        assert waiter_id == 7
        return make_confirmed_qr_order()

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(
        user_service,
        "find_service_order_user_by_pin",
        find_service_order_user_by_pin,
    )
    monkeypatch.setattr(
        order_service,
        "confirm_pending_qr_order",
        confirm_pending_qr_order,
    )

    response = client.post(
        "/api/v1/qr/orders/1/confirm",
        json={"pin": "1234"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"
    assert response.json()["waiter_id"] == 7
    assert response.json()["estimated_time"] == 15


def test_confirm_qr_pending_order_rejects_invalid_pin(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_pending_qr_order()

    async def find_service_order_user_by_pin(_db, *, pin: str):
        assert pin == "9999"
        return None

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(
        user_service,
        "find_service_order_user_by_pin",
        find_service_order_user_by_pin,
    )

    response = client.post(
        "/api/v1/qr/orders/1/confirm",
        json={"pin": "9999"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid PIN."


def test_reject_qr_pending_order_uses_pin_user(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_pending_qr_order()

    async def find_service_order_user_by_pin(_db, *, pin: str):
        assert pin == "1234"
        return make_user("WAITER")

    async def reject_pending_qr_order(_db, *, order, waiter_id: int, reason: str | None):
        assert order.id == 1
        assert waiter_id == 7
        assert reason == "Guest left the table"
        return make_rejected_qr_order()

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(
        user_service,
        "find_service_order_user_by_pin",
        find_service_order_user_by_pin,
    )
    monkeypatch.setattr(
        order_service,
        "reject_pending_qr_order",
        reject_pending_qr_order,
    )

    response = client.post(
        "/api/v1/qr/orders/1/reject",
        json={
            "pin": "1234",
            "reason": "Guest left the table",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["waiter_id"] == 7
