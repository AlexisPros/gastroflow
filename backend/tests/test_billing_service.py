import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.billing_service import billing_service
from app.services.order_service import OrderService


class FakeResult:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self) -> list[Any]:
        return self.rows


class FakeMergeSession:
    def __init__(self, item: OrderItem) -> None:
        self.results = [
            FakeResult(),
            FakeResult(),
            FakeResult(),
            FakeResult(rows=[item]),
        ]
        self.added: list[Any] = []

    async def execute(self, _statement: Any) -> FakeResult:
        return self.results.pop(0)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


def make_order(*, order_id: int, table_id: int, source: str = "WAITER") -> Order:
    return Order(
        id=order_id,
        version=1,
        table_id=table_id,
        waiter_id=1,
        source=source,
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        total_amount=Decimal("25.00"),
        subtotal_amount=Decimal("25.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
    )


def test_merge_releases_source_table_and_links_qr_order(monkeypatch):
    target_order = make_order(order_id=10, table_id=1)
    source_order = make_order(order_id=20, table_id=2, source="QR")
    item = OrderItem(
        id=100,
        order_id=source_order.id,
        product_id=1,
        quantity=1,
        unit_price=Decimal("25.00"),
        total_price=Decimal("25.00"),
        status="PENDING",
    )
    db = FakeMergeSession(item)
    released_tables: list[int | None] = []
    events: list[dict[str, Any]] = []

    async def release_table(_self, _db, *, order, table_id=None):
        assert order is source_order
        released_tables.append(table_id)

    async def recalculate_total(_self, _db, *, order):
        assert order is target_order
        return order

    async def broadcast_many(*, channels, event, data):
        events.append({"channels": channels, "event": event, "data": data})

    monkeypatch.setattr(OrderService, "_release_table_if_no_active_orders", release_table)
    monkeypatch.setattr(OrderService, "recalculate_total", recalculate_total)
    monkeypatch.setattr(websocket_manager, "broadcast_many", broadcast_many)

    merged_order = asyncio.run(
        billing_service.merge_orders(
            cast(AsyncSession, db),
            target_order=target_order,
            source_order=source_order,
            user_id=1,
        )
    )

    assert merged_order is target_order
    assert item.order_id == target_order.id
    assert source_order.status == "MERGED"
    assert source_order.qr_parent_order_id == target_order.id
    assert released_tables == [source_order.table_id]
    assert events == [
        {
            "channels": ["waiters", "floor"],
            "event": "orders_merged",
            "data": {
                "target_order_id": target_order.id,
                "source_order_id": source_order.id,
                "target_table_id": target_order.table_id,
                "source_table_id": source_order.table_id,
            },
        }
    ]
