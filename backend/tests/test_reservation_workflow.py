import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import order as crud_order
from app.core.websocket_manager import websocket_manager
from app.models.order import Order
from app.schemas.reservation import ReservationCreate
from app.services.payment_service import payment_service
from app.services.reservation_service import reservation_service


def test_reservation_requires_unique_tables() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ReservationCreate(
            table_ids=[1, 1],
            customer_name="Jan Kowalski",
            customer_phone="123456789",
            guest_count=2,
            reservation_time=datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc),
        )


def test_reservation_accepts_optional_preorder_and_email() -> None:
    reservation = ReservationCreate(
        table_ids=[1, 2],
        customer_name="Jan Kowalski",
        customer_phone="123456789",
        customer_email="jan@example.com",
        guest_count=6,
        reservation_time=datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc),
        items=[{"product_id": 4, "quantity": 2}],
        payment_method="CARD",
    )

    assert reservation.customer_email == "jan@example.com"
    assert reservation.items[0].quantity == 2
    assert reservation.duration_minutes == 120


def test_cash_prepaid_reservation_accepts_nip_and_received_cash() -> None:
    reservation = ReservationCreate(
        table_ids=[1],
        customer_name="Jan Kowalski",
        customer_phone="123456789",
        invoice_nip="1234567890",
        guest_count=2,
        reservation_time=datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc),
        items=[{"product_id": 4, "quantity": 2}],
        payment_method="CASH",
        cash_received=Decimal("100.00"),
    )

    assert reservation.invoice_nip == "1234567890"
    assert reservation.cash_received == Decimal("100.00")


def test_fully_prepaid_reservation_closes_without_second_payment(monkeypatch) -> None:
    order = Order(
        id=10,
        waiter_id=1,
        status="OPEN",
        total_amount=Decimal("80.00"),
        reservation_prepaid_amount=Decimal("80.00"),
    )

    class Result:
        def scalar_one_or_none(self):
            return order

    class EmptyPaymentResult:
        class Scalars:
            def first(self):
                return None

        def scalars(self):
            return self.Scalars()

    class FakeDb:
        def __init__(self):
            self.results = [Result(), EmptyPaymentResult()]

        async def execute(self, _query):
            return self.results.pop(0)

        def add(self, _obj: Any):
            return None

        async def commit(self):
            return None

        async def refresh(self, _obj: Any):
            return None

    async def release(_db, *, order):
        assert order.id == 10

    async def broadcast_many(**_kwargs):
        return None

    monkeypatch.setattr(crud_order, "_release_table_if_no_active_orders", release)
    monkeypatch.setattr(websocket_manager, "broadcast_many", broadcast_many)

    closed_order, payments, change = asyncio.run(
        payment_service.close_order_with_payments(
            cast(AsyncSession, FakeDb()),
            order_id=10,
            user_id=1,
            payments=[],
        )
    )

    assert closed_order.status == "CLOSED"
    assert payments == []
    assert change == Decimal("0.00")


def test_complete_prepaid_reservation_delegates_without_second_payment(monkeypatch) -> None:
    reservation = type(
        "ReservationStub",
        (),
        {
            "status": "STARTED",
            "started_order_id": 44,
            "prepaid_amount": Decimal("80.00"),
            "total_amount": Decimal("80.00"),
        },
    )()
    closed_order = Order(id=44, waiter_id=7, status="CLOSED", total_amount=Decimal("80.00"))
    received: dict[str, Any] = {}

    async def close_order_with_payments(_db, **kwargs):
        received.update(kwargs)
        return closed_order, [], Decimal("0.00")

    monkeypatch.setattr(payment_service, "close_order_with_payments", close_order_with_payments)

    result = asyncio.run(
        reservation_service.complete_prepaid(
            cast(AsyncSession, object()),
            reservation=reservation,
            user_id=7,
            user_role="WAITER",
        )
    )

    assert result is closed_order
    assert received == {
        "order_id": 44,
        "user_id": 7,
        "can_manage_all": False,
        "payments": [],
    }
