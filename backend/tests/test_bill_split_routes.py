from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import order as crud_order
from app.main import app
from app.models.order import Order
from app.models.user import User
from app.schemas.bill_split import (
    BillSegmentRead,
    BillSplitOriginalItemRead,
    BillSplitViewRead,
)
from app.services import bill_split_service


client = TestClient(app)


def make_user(role: str = "WAITER") -> User:
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
        split_parent_order_id=None,
        split_sequence=None,
        source="WAITER",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("40.00"),
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
        estimated_time=20,
    )


def make_bill_split_view() -> BillSplitViewRead:
    return BillSplitViewRead(
        order_id=1,
        original_items=[
            BillSplitOriginalItemRead(
                id=10,
                product_id=2,
                product_name="Lemoniada",
                quantity=Decimal("2.000"),
                assigned_quantity=Decimal("1.000"),
                remaining_quantity=Decimal("1.000"),
                unit_price=Decimal("12.00"),
                total_price=Decimal("24.00"),
                notes=None,
            ),
        ],
        segments=[
            BillSegmentRead(
                id=7,
                order_id=1,
                name="Check 1",
                position=0,
                status="OPEN",
                total_amount=Decimal("12.00"),
                created_at=datetime.now(timezone.utc),
                items=[],
            ),
        ],
        unassigned_total=Decimal("12.00"),
    )


def override_current_user(role: str = "WAITER") -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def patch_order(monkeypatch) -> None:
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    monkeypatch.setattr(crud_order, "get", get)


def test_get_bill_split_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def get_view(_db, *, order):
        assert order.id == 1
        return make_bill_split_view()

    monkeypatch.setattr(bill_split_service, "get_view", get_view)
    override_current_user()

    try:
        response = client.get(
            "/api/v1/orders/1/bill-split",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["order_id"] == 1
    assert response.json()["segments"][0]["id"] == 7


def test_create_bill_segment_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def create_segment(_db, *, order):
        assert order.id == 1
        return SimpleNamespace(id=7)

    async def get_view(_db, *, order):
        assert order.id == 1
        return make_bill_split_view()

    monkeypatch.setattr(bill_split_service, "create_segment", create_segment)
    monkeypatch.setattr(bill_split_service, "get_view", get_view)
    override_current_user()

    try:
        response = client.post(
            "/api/v1/orders/1/bill-split/segments",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 7


def test_move_bill_split_items_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def move_items(_db, *, order, target_segment_id, items):
        assert order.id == 1
        assert target_segment_id == 7
        assert items[0].order_item_id == 10
        assert items[0].quantity == Decimal("1")
        return make_bill_split_view()

    monkeypatch.setattr(bill_split_service, "move_items", move_items)
    override_current_user()

    try:
        response = client.post(
            "/api/v1/orders/1/bill-split/move-items",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "target_segment_id": 7,
                "items": [{"order_item_id": 10, "quantity": "1"}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["unassigned_total"] == "12.00"


def test_split_bill_item_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def split_item(_db, *, order, order_item_id, target_segment_ids):
        assert order.id == 1
        assert order_item_id == 10
        assert target_segment_ids == [7, 8]
        return make_bill_split_view()

    monkeypatch.setattr(bill_split_service, "split_item", split_item)
    override_current_user()

    try:
        response = client.post(
            "/api/v1/orders/1/bill-split/split-item",
            headers={"Authorization": "Bearer fake-token"},
            json={"order_item_id": 10, "target_segment_ids": [7, 8]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["order_id"] == 1


def test_delete_empty_bill_segment_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def delete_segment(_db, *, order, segment_id):
        assert order.id == 1
        assert segment_id == 7

    monkeypatch.setattr(bill_split_service, "delete_segment", delete_segment)
    override_current_user()

    try:
        response = client.delete(
            "/api/v1/orders/1/bill-split/segments/7",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204


def test_finalize_bill_split_reaches_service(monkeypatch):
    patch_order(monkeypatch)

    async def finalize(_db, *, order, segment_guest_counts):
        assert order.id == 1
        assert segment_guest_counts == {7: 2}
        split_order = make_order()
        split_order.id = 2
        split_order.split_parent_order_id = 1
        split_order.split_sequence = 1
        split_order.guest_count = 2
        return [split_order]

    monkeypatch.setattr(bill_split_service, "finalize", finalize)
    override_current_user()

    try:
        response = client.post(
            "/api/v1/orders/1/bill-split/finalize",
            headers={"Authorization": "Bearer fake-token"},
            json={"segment_guest_counts": [{"segment_id": 7, "guest_count": 2}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["id"] == 2
    assert response.json()[0]["split_parent_order_id"] == 1
    assert response.json()[0]["split_sequence"] == 1
