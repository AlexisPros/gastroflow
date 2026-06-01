import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud import kitchen_task as crud_kitchen_task
from app.crud import order as crud_order
from app.crud import order_item as crud_order_item
from app.crud import payment as crud_payment
from app.crud import stock_item as crud_stock_item
from app.main import app
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.services import kitchen_service, payment_service, stock_service


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


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


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


def make_stock_item() -> StockItem:
    return StockItem(
        id=1,
        warehouse_id=1,
        ingredient_id=1,
        quantity=Decimal("10.00"),
        minimum_quantity=Decimal("1.00"),
    )


def make_stock_movement() -> StockMovement:
    return StockMovement(
        id=1,
        stock_item_id=1,
        type="DELIVERY",
        quantity=Decimal("5.00"),
        created_at=datetime.now(timezone.utc),
        description="Test movement",
    )


def make_order_item() -> OrderItem:
    return OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=2,
        unit_price=Decimal("10.00"),
        total_price=Decimal("20.00"),
        status="NEW",
        notes=None,
    )


def test_kitchen_task_start_forbidden_for_waiter():
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/start",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_kitchen_task_start_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_kitchen_task()

    async def start_task(_db, *, task):
        assert task.id == 1
        task.status = "IN_PROGRESS"
        task.started_at = datetime.now(timezone.utc)
        return task

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    monkeypatch.setattr(kitchen_service, "start_task", start_task)
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/start",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["started_at"] is not None


def test_kitchen_task_complete_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        task = make_kitchen_task()
        task.status = "IN_PROGRESS"
        task.started_at = datetime.now(timezone.utc)
        return task

    async def complete_task(_db, *, task):
        assert task.id == 1
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        return task

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    monkeypatch.setattr(kitchen_service, "complete_task", complete_task)
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/complete",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["completed_at"] is not None


def test_payment_register_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def register_payment(_db, *, order, method, amount, close_order):
        assert order.id == 1
        assert method == "CARD"
        assert amount == Decimal("25.00")
        assert close_order is True
        return make_payment()

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(payment_service, "register_payment", register_payment)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/payments",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "method": "CARD",
                "amount": "25.00",
                "close_order": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["method"] == "CARD"
    assert response.json()["amount"] == "25.00"


def test_payment_register_with_close_order_uses_order_close(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []
            self.refreshed: list[Any] = []

        def add(self, obj: Any):
            self.added.append(obj)

        async def refresh(self, obj: Any):
            self.refreshed.append(obj)

    async def close(_db, *, db_obj):
        assert db_obj.id == 1
        db_obj.status = "CLOSED"
        db_obj.closed_at = datetime.now(timezone.utc)
        return db_obj

    monkeypatch.setattr(crud_order, "close", close)

    order = make_order()
    db = FakeDb()
    payment = asyncio.run(
        payment_service.register_payment(
            cast(AsyncSession, db),
            order=order,
            method="CARD",
            amount=Decimal("25.00"),
            close_order=True,
        ),
    )

    assert payment.method == "CARD"
    assert payment.amount == Decimal("25.00")
    assert order.status == "CLOSED"
    assert payment in db.added
    assert payment in db.refreshed


def test_payment_cancel_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_payment()

    async def cancel_payment(_db, *, payment):
        assert payment.id == 1
        payment.status = "CANCELLED"
        return payment

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

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_payment_refund_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_payment()

    async def refund_payment(_db, *, payment):
        assert payment.id == 1
        payment.status = "REFUNDED"
        return payment

    monkeypatch.setattr(crud_payment, "get", get)
    monkeypatch.setattr(payment_service, "refund_payment", refund_payment)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/payments/1/refund",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "REFUNDED"


def test_stock_apply_movement_forbidden_for_waiter():
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/stock-items/1/movements/apply",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "type": "DELIVERY",
                "quantity_delta": "5.00",
                "description": "Test movement",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_stock_apply_movement_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_stock_item()

    async def apply_movement(
        _db,
        *,
        stock_item,
        type,
        quantity_delta,
        description,
        prevent_negative,
    ):
        assert stock_item.id == 1
        assert type == "DELIVERY"
        assert quantity_delta == Decimal("5.00")
        assert description == "Test movement"
        assert prevent_negative is True
        return make_stock_movement()

    monkeypatch.setattr(crud_stock_item, "get", get)
    monkeypatch.setattr(stock_service, "apply_movement", apply_movement)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/stock-items/1/movements/apply",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "type": "DELIVERY",
                "quantity_delta": "5.00",
                "description": "Test movement",
                "prevent_negative": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["type"] == "DELIVERY"
    assert response.json()["quantity"] == "5.00"


def test_consume_stock_for_order_item_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order_item()

    async def consume_ingredients_for_order_item(_db, *, order_item, warehouse_id):
        assert order_item.id == 1
        assert warehouse_id == 1
        movement = make_stock_movement()
        movement.type = "CONSUMPTION"
        return [movement]

    monkeypatch.setattr(crud_order_item, "get", get)
    monkeypatch.setattr(
        stock_service,
        "consume_ingredients_for_order_item",
        consume_ingredients_for_order_item,
    )
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/order-items/1/consume-stock",
            headers={"Authorization": "Bearer fake-token"},
            json={"warehouse_id": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["type"] == "CONSUMPTION"
