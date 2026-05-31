from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.crud import restaurant_table as crud_restaurant_table
from app.main import app
from app.models.order import Order
from app.models.restaurant_table import RestaurantTable
from app.services import order_service


client = TestClient(app)


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
        table_id=1,
        waiter_id=None,
        discount_id=None,
        guest_count=2,
        source="QR",
        status="PENDING_CONFIRMATION",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("42.00"),
        tip_amount=Decimal("0.00"),
        estimated_time=None,
    )


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
