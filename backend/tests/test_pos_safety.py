import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud import order as crud_order
from app.crud import payment as crud_payment
from app.main import app
from app.models.order import Order
from app.models.payment import Payment
from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.services import bill_split_service, order_service, payment_service


client = TestClient(app)


def make_user(*, id: int = 1, role: str = "WAITER") -> User:
    return User(
        id=id,
        first_name="Test",
        last_name="User",
        email=f"user{id}@example.com",
        password_hash="hash",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def make_order(*, waiter_id: int = 1, status: str = "OPEN") -> Order:
    return Order(
        id=1,
        version=1,
        table_id=1,
        waiter_id=waiter_id,
        source="WAITER",
        status=status,
        total_amount=Decimal("25.00"),
        subtotal_amount=Decimal("25.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(*, id: int = 1, role: str = "WAITER") -> None:
    async def _get_current_user_override():
        return make_user(id=id, role=role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def test_waiter_cannot_add_items_to_another_waiters_order(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order(waiter_id=2)

    monkeypatch.setattr(crud_order, "get", get)
    override_current_user(id=1)

    try:
        response = client.post(
            "/api/v1/orders/1/items",
            headers={"Authorization": "Bearer fake-token"},
            json={"items": [{"product_id": 1, "quantity": 1}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_payment_method_change_requires_manager_pin_for_waiter(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return Payment(
            id=1,
            order_id=1,
            method="CARD",
            amount=Decimal("25.00"),
            status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(crud_payment, "get", get)
    override_current_user()

    try:
        response = client.post(
            "/api/v1/payments/1/toggle-method",
            headers={"Authorization": "Bearer fake-token"},
            json={"reason": "Guest requested correction"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Manager PIN is required."


def test_closed_order_cannot_be_split():
    order = make_order(status="CLOSED")

    with pytest.raises(ValueError, match="active order"):
        bill_split_service._ensure_order_can_split(order)


def test_occupied_table_cannot_receive_new_waiter_order():
    table = RestaurantTable(
        id=1,
        table_number="1",
        status="OCCUPIED",
        is_active=True,
    )

    class Result:
        def scalar_one_or_none(self):
            return table

    class FakeDb:
        async def execute(self, _query):
            return Result()

    with pytest.raises(ValueError, match="not free"):
        asyncio.run(
            order_service._ensure_table_accepts_waiter_order(
                cast(AsyncSession, FakeDb()),
                table_id=1,
            ),
        )


def test_order_cannot_close_with_incorrect_payment_total():
    order = make_order()

    class OrderResult:
        def scalar_one_or_none(self):
            return order

    class ExistingPaymentResult:
        class Scalars:
            def first(self):
                return None

        def scalars(self):
            return self.Scalars()

    class FakeDb:
        def __init__(self):
            self.results = [OrderResult(), ExistingPaymentResult()]
            self.added: list[Any] = []

        async def execute(self, _query):
            return self.results.pop(0)

        def add(self, obj: Any):
            self.added.append(obj)

    with pytest.raises(ValueError, match="exactly match"):
        asyncio.run(
            payment_service.close_order_with_payments(
                cast(AsyncSession, FakeDb()),
                order_id=1,
                user_id=1,
                payments=[
                    {
                        "method": "CARD",
                        "amount": Decimal("24.00"),
                    },
                ],
            ),
        )


def test_mixed_payment_close_route_returns_change(monkeypatch):
    async def close_order_with_payments(
        _db,
        *,
        order_id: int,
        user_id: int,
        can_manage_all: bool,
        payments: list[dict],
    ):
        assert order_id == 1
        assert user_id == 1
        assert can_manage_all is False
        assert [item["method"] for item in payments] == ["CARD", "CASH"]

        order = make_order(status="CLOSED")
        card = Payment(
            id=1,
            order_id=1,
            method="CARD",
            amount=Decimal("15.00"),
            status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )
        cash = Payment(
            id=2,
            order_id=1,
            method="CASH",
            amount=Decimal("10.00"),
            cash_received=Decimal("20.00"),
            change_given=Decimal("10.00"),
            status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )
        return order, [card, cash], Decimal("10.00")

    monkeypatch.setattr(
        payment_service,
        "close_order_with_payments",
        close_order_with_payments,
    )
    override_current_user()

    try:
        response = client.post(
            "/api/v1/orders/1/close-with-payments",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "payments": [
                    {"method": "CARD", "amount": "15.00"},
                    {
                        "method": "CASH",
                        "amount": "10.00",
                        "cash_received": "20.00",
                    },
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["change_due"] == "10.00"
    assert response.json()["payments"][1]["change_given"] == "10.00"


def test_payment_close_retry_returns_existing_payments():
    order = make_order(status="CLOSED")
    payment = Payment(
        id=1,
        order_id=order.id,
        idempotency_key="payment-retry-key",
        method="CASH",
        amount=Decimal("25.00"),
        cash_received=Decimal("30.00"),
        change_given=Decimal("5.00"),
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )

    class OrderResult:
        def scalar_one_or_none(self):
            return order

    class PaymentResult:
        class Scalars:
            def all(self):
                return [payment]

        def scalars(self):
            return self.Scalars()

    class FakeDb:
        def __init__(self):
            self.results = [OrderResult(), PaymentResult()]

        async def execute(self, _query):
            return self.results.pop(0)

    result_order, payments, change = asyncio.run(
        payment_service.close_order_with_payments(
            cast(AsyncSession, FakeDb()),
            order_id=order.id,
            user_id=order.waiter_id,
            payments=[
                {
                    "method": "CASH",
                    "amount": Decimal("25.00"),
                    "cash_received": Decimal("30.00"),
                    "idempotency_key": "payment-retry-key",
                },
            ],
        ),
    )

    assert result_order is order
    assert payments == [payment]
    assert change == Decimal("5.00")


def test_payment_method_toggle_clears_cash_fields_when_changed_to_card():
    order = make_order(status="CLOSED")
    payment = Payment(
        id=1,
        order_id=order.id,
        method="CASH",
        amount=Decimal("25.00"),
        cash_received=Decimal("30.00"),
        change_given=Decimal("5.00"),
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )

    class OrderResult:
        def scalar_one_or_none(self):
            return order

    class OtherPaymentsResult:
        class Scalars:
            def first(self):
                return None

        def scalars(self):
            return self.Scalars()

    class FakeDb:
        def __init__(self):
            self.results = [OrderResult(), OtherPaymentsResult()]

        async def execute(self, _query):
            return self.results.pop(0)

        def add(self, _obj):
            pass

        async def commit(self):
            pass

        async def refresh(self, _obj):
            pass

    updated = asyncio.run(
        payment_service.toggle_payment_method(
            cast(AsyncSession, FakeDb()),
            payment=payment,
            user_id=order.waiter_id,
            authorized_user_id=order.waiter_id,
            can_manage_all=True,
            reason="Correction",
        ),
    )

    assert updated.method == "CARD"
    assert updated.cash_received is None
    assert updated.change_given is None
