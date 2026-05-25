from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import order as crud_order
from app.main import app
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.order_transfer_log import OrderTransferLog
from app.models.user import User
from app.services import discount_service, order_service


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
        source="WAITER",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("25.00"),
        tip_amount=Decimal("0.00"),
    )


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def test_create_order_with_items_forbidden_for_kitchen_role():
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/orders/with-items",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "table_id": 1,
                "waiter_id": 1,
                "source": "WAITER",
                "items": [
                    {
                        "product_id": 1,
                        "quantity": 2,
                        "notes": "No onion",
                        "product_modifier_ids": [1],
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_order_with_items_reaches_service(monkeypatch):
    async def create_order_with_items(
        _db,
        *,
        table_id,
        waiter_id,
        source,
        items,
    ):
        assert table_id == 1
        assert waiter_id == 1
        assert source == "WAITER"
        assert len(items) == 1
        assert items[0].product_id == 1
        assert items[0].quantity == 2
        assert items[0].notes == "No onion"
        assert items[0].product_modifier_ids == [1]
        return make_order()

    monkeypatch.setattr(
        order_service,
        "create_order_with_items",
        create_order_with_items,
    )
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/with-items",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "table_id": 1,
                "waiter_id": 1,
                "source": "WAITER",
                "items": [
                    {
                        "product_id": 1,
                        "quantity": 2,
                        "notes": "No onion",
                        "product_modifier_ids": [1],
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["total_amount"] == "25.00"


def test_close_order_reaches_crud(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def close(_db, *, db_obj):
        assert db_obj.id == 1
        db_obj.status = "CLOSED"
        db_obj.closed_at = datetime.now(timezone.utc)
        return db_obj

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(crud_order, "close", close)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/close",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"
    assert response.json()["closed_at"] is not None


def test_apply_discount_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def apply_discount(_db, *, order, discount_id: int):
        assert order.id == 1
        assert discount_id == 2
        order.discount_id = discount_id
        order.total_amount = Decimal("20.00")
        return order

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(discount_service, "apply_discount", apply_discount)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/orders/1/discount",
            headers={"Authorization": "Bearer fake-token"},
            json={"discount_id": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["discount_id"] == 2
    assert response.json()["total_amount"] == "20.00"


def test_transfer_order_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def transfer_order(_db, *, order, to_waiter_id: int):
        assert order.id == 1
        assert to_waiter_id == 2
        return OrderTransferLog(
            id=1,
            order_id=order.id,
            from_waiter_id=order.waiter_id,
            to_waiter_id=to_waiter_id,
            transferred_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(order_service, "transfer_order", transfer_order)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/orders/1/transfer",
            headers={"Authorization": "Bearer fake-token"},
            json={"to_waiter_id": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["order_id"] == 1
    assert response.json()["from_waiter_id"] == 1
    assert response.json()["to_waiter_id"] == 2


def test_record_order_action_reaches_service(monkeypatch):
    async def record_action(
        _db,
        *,
        order_id: int,
        user_id: int,
        action_type: str,
        description: str | None = None,
    ):
        assert order_id == 1
        assert user_id == 1
        assert action_type == "NOTE"
        assert description == "Customer asked for water"
        return OrderActionLog(
            id=1,
            order_id=order_id,
            user_id=user_id,
            action_type=action_type,
            description=description,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(order_service, "record_action", record_action)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/actions",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "user_id": 1,
                "action_type": "NOTE",
                "description": "Customer asked for water",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["action_type"] == "NOTE"
    assert response.json()["description"] == "Customer asked for water"
