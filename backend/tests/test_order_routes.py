import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud import order as crud_order
from app.crud import product_kitchen_step as product_kitchen_step_crud
from app.main import app
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_kitchen_step import ProductKitchenStep
from app.models.order_transfer_log import OrderTransferLog
from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.services import discount_service, order_service
from app.services.order_service import OrderItemRequest


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
        subtotal_amount=Decimal("28.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
        estimated_time=20,
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
        guest_count,
        source,
        items,
    ):
        assert table_id == 1
        assert waiter_id == 1
        assert guest_count == 3
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
                "guest_count": 3,
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


def test_add_items_to_order_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def add_items_to_order(_db, *, order, items):
        assert order.id == 1
        assert len(items) == 1
        assert items[0].product_id == 2
        assert items[0].quantity == 1
        assert items[0].position == 0
        assert items[0].course_number == 2
        assert items[0].notes == "Medium rare"
        assert items[0].product_modifier_ids == [3]
        order.subtotal_amount = Decimal("45.00")
        order.total_amount = Decimal("45.00")
        return order

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(order_service, "add_items_to_order", add_items_to_order)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/items",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "items": [
                    {
                        "product_id": 2,
                        "quantity": 1,
                        "position": 0,
                        "course_number": 2,
                        "notes": "Medium rare",
                        "product_modifier_ids": [3],
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["total_amount"] == "45.00"


def test_cancel_order_with_manager_pin_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def cancel_order_with_manager_pin(_db, *, order, manager_pin: str):
        assert order.id == 1
        assert manager_pin == "2468"
        order.status = "CANCELLED"
        return order

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(
        order_service,
        "cancel_order_with_manager_pin",
        cancel_order_with_manager_pin,
    )
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/cancel",
            headers={"Authorization": "Bearer fake-token"},
            json={"manager_pin": "2468"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_verify_manager_pin_reaches_service(monkeypatch):
    async def verify_manager_pin(_db, *, manager_pin: str):
        assert manager_pin == "2468"
        return make_user("MANAGER")

    monkeypatch.setattr(order_service, "verify_manager_pin", verify_manager_pin)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/manager-pin/verify",
            headers={"Authorization": "Bearer fake-token"},
            json={"manager_pin": "2468"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_void_order_item_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_order()

    async def void_order_item(
        _db,
        *,
        order,
        order_item_id: int,
        current_user,
        manager_pin: str | None = None,
    ):
        assert order.id == 1
        assert order_item_id == 7
        assert current_user.role == "WAITER"
        assert manager_pin == "2468"
        order.total_amount = Decimal("15.00")
        return order

    monkeypatch.setattr(crud_order, "get", get)
    monkeypatch.setattr(order_service, "void_order_item", void_order_item)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/orders/1/items/7/void",
            headers={"Authorization": "Bearer fake-token"},
            json={"manager_pin": "2468"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total_amount"] == "15.00"


def test_order_item_creates_kitchen_task_for_each_product_step(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []

        def add(self, obj: Any):
            self.added.append(obj)

        async def flush(self):
            return None

    product = Product(
        id=1,
        category_id=1,
        kitchen_section_id=None,
        name="Salatka cezar",
        description=None,
        price=Decimal("28.00"),
        preparation_time=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    steps = [
        ProductKitchenStep(
            id=1,
            product_id=1,
            kitchen_section_id=2,
            name="Przygotowanie salatki",
            sequence=1,
            estimated_time=7,
            is_active=True,
        ),
        ProductKitchenStep(
            id=2,
            product_id=1,
            kitchen_section_id=3,
            name="Przygotowanie dodatku miesnego",
            sequence=2,
            estimated_time=8,
            is_active=True,
        ),
    ]

    async def get_active_product(_db, *, product_id: int):
        assert product_id == 1
        return product

    async def get_active_by_product(_db, *, product_id: int):
        assert product_id == 1
        return steps

    async def get_existing_kitchen_task_estimated_time(_db, *, order_item_id: int):
        assert order_item_id == 1
        return False, None

    monkeypatch.setattr(order_service, "_get_active_product", get_active_product)
    monkeypatch.setattr(
        order_service,
        "_get_existing_kitchen_task_estimated_time",
        get_existing_kitchen_task_estimated_time,
    )
    monkeypatch.setattr(
        product_kitchen_step_crud,
        "get_active_by_product",
        get_active_by_product,
    )

    db = FakeDb()
    order_item = OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=1,
        unit_price=Decimal("28.00"),
        total_price=Decimal("28.00"),
        status="NEW",
        notes=None,
    )

    estimated_time = asyncio.run(
        order_service._create_kitchen_task_for_item(
            cast(AsyncSession, db),
            order_item=order_item,
        ),
    )

    assert len(db.added) == 2
    assert [task.kitchen_section_id for task in db.added] == [2, 3]
    assert [task.product_kitchen_step_id for task in db.added] == [1, 2]
    assert estimated_time == 8


def test_order_item_does_not_duplicate_existing_kitchen_tasks(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []

        def add(self, obj: Any):
            self.added.append(obj)

    async def get_existing_kitchen_task_estimated_time(_db, *, order_item_id: int):
        assert order_item_id == 1
        return True, 12

    async def get_active_product(_db, *, product_id: int):
        raise AssertionError("Product should not be loaded when tasks already exist.")

    monkeypatch.setattr(
        order_service,
        "_get_existing_kitchen_task_estimated_time",
        get_existing_kitchen_task_estimated_time,
    )
    monkeypatch.setattr(order_service, "_get_active_product", get_active_product)

    db = FakeDb()
    order_item = OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=1,
        unit_price=Decimal("28.00"),
        total_price=Decimal("28.00"),
        status="NEW",
        notes=None,
    )

    estimated_time = asyncio.run(
        order_service._create_kitchen_task_for_item(
            cast(AsyncSession, db),
            order_item=order_item,
        ),
    )

    assert db.added == []
    assert estimated_time == 12


def test_confirm_pending_qr_order_records_action_log(monkeypatch):
    class FakeResult:
        def __init__(self, values: list[Any] | None = None, value: Any = None):
            self.values = values
            self.value = value

        def scalars(self):
            return self

        def all(self):
            return self.values

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self, order_items, table):
            self.order_items = order_items
            self.table = table
            self.execute_count = 0
            self.added: list[Any] = []
            self.committed = False

        async def execute(self, _statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return FakeResult(values=self.order_items)

            return FakeResult(value=self.table)

        def add(self, obj: Any):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, _obj):
            return None

    order = Order(
        id=1,
        table_id=1,
        waiter_id=None,
        discount_id=None,
        shift_id=None,
        source="QR",
        status="PENDING_CONFIRMATION",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("28.00"),
        subtotal_amount=Decimal("28.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
    )
    order_item = OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=1,
        unit_price=Decimal("28.00"),
        total_price=Decimal("28.00"),
        status="NEW",
        notes=None,
    )

    async def create_kitchen_task_for_item(_db, *, order_item):
        assert order_item.id == 1
        return 9

    monkeypatch.setattr(
        order_service,
        "_create_kitchen_task_for_item",
        create_kitchen_task_for_item,
    )

    table = RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="PENDING_ORDER",
        qr_code_url="http://localhost:3000/qr/a1-token",
        qr_token="a1-token",
        is_active=True,
    )
    db = FakeDb([order_item], table)
    confirmed_order = asyncio.run(
        order_service.confirm_pending_qr_order(
            cast(AsyncSession, db),
            order=order,
            waiter_id=7,
        ),
    )

    action_logs = [
        obj
        for obj in db.added
        if isinstance(obj, OrderActionLog)
    ]
    assert confirmed_order.status == "OPEN"
    assert confirmed_order.waiter_id == 7
    assert confirmed_order.estimated_time == 9
    assert table.status == "OCCUPIED"
    assert len(action_logs) == 1
    assert action_logs[0].action_type == "QR_ORDER_CONFIRMED"
    assert action_logs[0].user_id == 7
    assert db.committed is True


def test_reject_pending_qr_order_records_action_log():
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self, table):
            self.table = table
            self.added: list[Any] = []
            self.committed = False

        async def execute(self, _statement):
            return FakeResult(self.table)

        def add(self, obj: Any):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, _obj):
            return None

    order = Order(
        id=1,
        table_id=1,
        waiter_id=None,
        discount_id=None,
        shift_id=None,
        source="QR",
        status="PENDING_CONFIRMATION",
        created_at=datetime.now(timezone.utc),
        closed_at=None,
        total_amount=Decimal("28.00"),
        subtotal_amount=Decimal("25.00"),
        discount_amount=Decimal("0.00"),
        tip_amount=Decimal("0.00"),
    )

    table = RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="PENDING_ORDER",
        qr_code_url="http://localhost:3000/qr/a1-token",
        qr_token="a1-token",
        is_active=True,
    )
    db = FakeDb(table)
    rejected_order = asyncio.run(
        order_service.reject_pending_qr_order(
            cast(AsyncSession, db),
            order=order,
            waiter_id=7,
            reason="Guest left the table",
        ),
    )

    action_logs = [
        obj
        for obj in db.added
        if isinstance(obj, OrderActionLog)
    ]
    assert rejected_order.status == "REJECTED"
    assert rejected_order.waiter_id == 7
    assert table.status == "FREE"
    assert len(action_logs) == 1
    assert action_logs[0].action_type == "QR_ORDER_REJECTED"
    assert action_logs[0].description == "Guest left the table"
    assert db.committed is True


def test_create_pending_qr_order_rejects_occupied_table():
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []

        async def execute(self, _statement):
            return FakeResult(
                RestaurantTable(
                    id=1,
                    table_number="A1",
                    current_guests=2,
                    status="OCCUPIED",
                    qr_code_url="http://localhost:3000/qr/a1-token",
                    qr_token="a1-token",
                    is_active=True,
                ),
            )

        def add(self, obj: Any):
            self.added.append(obj)

    db = FakeDb()

    try:
        asyncio.run(
            order_service.create_pending_qr_order(
                cast(AsyncSession, db),
                table_id=1,
                guest_count=2,
                items=[
                    OrderItemRequest(
                        product_id=1,
                        quantity=1,
                    ),
                ],
            ),
        )
    except ValueError as exc:
        assert str(exc) == "Restaurant table is not free."
    else:
        raise AssertionError("Expected occupied table to reject QR order.")

    assert db.added == []


def test_create_pending_qr_order_rejects_table_with_active_order():
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.execute_count = 0
            self.added: list[Any] = []

        async def execute(self, _statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return FakeResult(
                    RestaurantTable(
                        id=1,
                        table_number="A1",
                        current_guests=None,
                        status="FREE",
                        qr_code_url="http://localhost:3000/qr/a1-token",
                        qr_token="a1-token",
                        is_active=True,
                    ),
                )

            return FakeResult(make_order())

        def add(self, obj: Any):
            self.added.append(obj)

    db = FakeDb()

    try:
        asyncio.run(
            order_service.create_pending_qr_order(
                cast(AsyncSession, db),
                table_id=1,
                guest_count=2,
                items=[
                    OrderItemRequest(
                        product_id=1,
                        quantity=1,
                    ),
                ],
            ),
        )
    except ValueError as exc:
        assert str(exc) == "Restaurant table already has an active order."
    else:
        raise AssertionError("Expected active table order to reject QR order.")

    assert db.added == []


def test_create_pending_qr_order_sets_table_pending_status(monkeypatch):
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self, table):
            self.table = table
            self.execute_count = 0
            self.added: list[Any] = []
            self.committed = False

        async def execute(self, _statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return FakeResult(self.table)

            return FakeResult(None)

        def add(self, obj: Any):
            self.added.append(obj)

        async def flush(self):
            return None

        async def commit(self):
            self.committed = True

        async def refresh(self, _obj):
            return None

    async def create_order_item(_db, *, order_id, item_request):
        return (
            OrderItem(
                id=1,
                order_id=order_id,
                product_id=item_request.product_id,
                quantity=item_request.quantity,
                unit_price=Decimal("28.00"),
                total_price=Decimal("28.00"),
                status="NEW",
                notes=None,
            ),
            Decimal("28.00"),
        )

    monkeypatch.setattr(order_service, "_create_order_item", create_order_item)

    table = RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="FREE",
        qr_code_url="http://localhost:3000/qr/a1-token",
        qr_token="a1-token",
        is_active=True,
    )
    db = FakeDb(table)

    order = asyncio.run(
        order_service.create_pending_qr_order(
            cast(AsyncSession, db),
            table_id=1,
            guest_count=2,
            items=[
                OrderItemRequest(
                    product_id=1,
                    quantity=1,
                ),
            ],
        ),
    )

    assert order.status == "PENDING_CONFIRMATION"
    assert table.status == "PENDING_ORDER"
    assert table in db.added
    assert db.committed is True


def test_product_estimated_time_uses_longest_parallel_step():
    estimated_time = order_service._calculate_product_estimated_time(
        [7, 10, None],
    )

    assert estimated_time == 10


def test_close_order_releases_table_when_no_other_active_orders():
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self, table):
            self.table = table
            self.execute_count = 0
            self.added: list[Any] = []
            self.committed = False

        async def execute(self, _statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return FakeResult(None)

            return FakeResult(self.table)

        def add(self, obj: Any):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, _obj):
            return None

    order = make_order()
    table = RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=2,
        status="OCCUPIED",
        qr_code_url="http://localhost:3000/qr/a1-token",
        qr_token="a1-token",
        is_active=True,
    )
    db = FakeDb(table)

    closed_order = asyncio.run(
        crud_order.close(
            cast(AsyncSession, db),
            db_obj=order,
        ),
    )

    assert closed_order.status == "CLOSED"
    assert closed_order.closed_at is not None
    assert table.status == "FREE"
    assert table.current_guests is None
    assert table in db.added
    assert db.committed is True


def test_close_order_keeps_table_occupied_when_other_order_is_active():
    class FakeResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []
            self.committed = False

        async def execute(self, _statement):
            other_order = make_order()
            other_order.id = 2
            return FakeResult(other_order)

        def add(self, obj: Any):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, _obj):
            return None

    order = make_order()
    db = FakeDb()

    closed_order = asyncio.run(
        crud_order.close(
            cast(AsyncSession, db),
            db_obj=order,
        ),
    )

    assert closed_order.status == "CLOSED"
    assert closed_order.closed_at is not None
    assert db.added == [order]
    assert db.committed is True


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
