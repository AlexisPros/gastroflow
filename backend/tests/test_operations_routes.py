import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.routes import kitchen as kitchen_routes
from app.core.websocket_manager import websocket_manager
from app.crud import kitchen_task as crud_kitchen_task
from app.crud import order as crud_order
from app.crud import order_item as crud_order_item
from app.crud import payment as crud_payment
from app.crud import restaurant_table as crud_restaurant_table
from app.crud import stock_item as crud_stock_item
from app.main import app
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product_kitchen_step import ProductKitchenStep
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
        kitchen_section_id=1 if role in {"KITCHEN", "BARTENDER"} else None,
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


def make_product_step(
    *,
    id: int,
    sequence: int,
    depends_on_sequence: int | None = None,
) -> ProductKitchenStep:
    return ProductKitchenStep(
        id=id,
        product_id=1,
        kitchen_section_id=id,
        name=f"Step {sequence}",
        description=None,
        sequence=sequence,
        estimated_time=5,
        depends_on_sequence=depends_on_sequence,
        is_active=True,
    )


def make_task_for_step(
    *,
    id: int,
    step: ProductKitchenStep,
    status: str = "PENDING",
) -> KitchenTask:
    return KitchenTask(
        id=id,
        order_item_id=1,
        kitchen_section_id=step.kitchen_section_id,
        product_kitchen_step_id=step.id,
        assigned_user_id=None,
        status=status,
        estimated_time=step.estimated_time,
        started_at=None,
        completed_at=None,
        product_kitchen_step=step,
    )


class FakeKitchenResult:
    def __init__(self, tasks: list[KitchenTask]) -> None:
        self.tasks = tasks

    def scalars(self):
        return self

    def all(self) -> list[KitchenTask]:
        return self.tasks


class FakeKitchenSession:
    def __init__(self, tasks: list[KitchenTask]) -> None:
        self.tasks = tasks
        self.commits = 0

    async def execute(self, _statement: Any) -> FakeKitchenResult:
        return FakeKitchenResult(self.tasks)

    def add(self, _obj: Any) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj: Any) -> None:
        return None


class FakeReadySession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


class FakeRouteResult:
    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self) -> list[Any]:
        return self.rows


class FakeCompleteOrderSession(FakeReadySession):
    def __init__(self, *, order: Any, tasks: list[KitchenTask]) -> None:
        super().__init__()
        self.results = [
            FakeRouteResult(scalar=order),
            FakeRouteResult(rows=tasks),
        ]

    async def execute(self, _statement: Any) -> FakeRouteResult:
        return self.results.pop(0)


def make_order() -> Order:
    return Order(
        id=1,
        version=1,
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


def test_bartender_cannot_start_kitchen_section_task(monkeypatch):
    task = make_kitchen_task()
    task.kitchen_section_id = 2

    async def get(_db, id: int):
        assert id == 1
        return task

    async def get_bar_section_id(_db):
        return 1

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    monkeypatch.setattr(kitchen_routes, "_get_bar_section_id", get_bar_section_id)
    override_current_user("BARTENDER")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/start",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Bartender can only access bar tasks."


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


def test_kitchen_task_start_requires_accepted_task():
    task = make_kitchen_task()

    try:
        asyncio.run(kitchen_service.start_task(cast(AsyncSession, None), task=task))
    except ValueError as exc:
        assert str(exc) == "Kitchen order must be accepted before the task can be started."
    else:
        raise AssertionError("NEW task was started before kitchen pass accepted the order.")


def test_kitchen_task_start_starts_parallel_steps(monkeypatch):
    step_one = make_product_step(id=1, sequence=1)
    step_two = make_product_step(id=2, sequence=2)
    dependent_step = make_product_step(id=3, sequence=3, depends_on_sequence=1)
    tasks = [
        make_task_for_step(id=1, step=step_one),
        make_task_for_step(id=2, step=step_two),
        make_task_for_step(id=3, step=dependent_step),
    ]
    db = FakeKitchenSession(tasks)
    events: list[tuple[str, int]] = []

    async def broadcast(*, event: str, task: KitchenTask) -> None:
        events.append((event, task.id))

    monkeypatch.setattr(kitchen_service, "_broadcast_task_event", broadcast)

    asyncio.run(kitchen_service.start_task(cast(AsyncSession, db), task=tasks[0]))

    assert tasks[0].status == "IN_PROGRESS"
    assert tasks[1].status == "IN_PROGRESS"
    assert tasks[2].status == "PENDING"
    assert db.commits == 1
    assert events == [
        ("kitchen_task_started", 1),
        ("kitchen_task_started", 2),
    ]


def test_kitchen_task_start_state_blocks_dependent_step():
    parent_step = make_product_step(id=1, sequence=1)
    child_step = make_product_step(id=2, sequence=2, depends_on_sequence=1)
    parent_task = make_task_for_step(id=1, step=parent_step, status="IN_PROGRESS")
    child_task = make_task_for_step(id=2, step=child_step)

    can_start, blocked_by = kitchen_service.get_task_start_state(
        task=child_task,
        tasks=[parent_task, child_task],
    )

    assert can_start is False
    assert blocked_by == "Step 1"


def test_kitchen_task_start_state_unlocks_after_dependency_completion():
    parent_step = make_product_step(id=1, sequence=1)
    child_step = make_product_step(id=2, sequence=2, depends_on_sequence=1)
    parent_task = make_task_for_step(id=1, step=parent_step, status="COMPLETED")
    child_task = make_task_for_step(id=2, step=child_step)

    can_start, blocked_by = kitchen_service.get_task_start_state(
        task=child_task,
        tasks=[parent_task, child_task],
    )

    assert can_start is True
    assert blocked_by is None


def test_bartender_can_start_new_bar_task_without_starting_kitchen_task(monkeypatch):
    bar_step = make_product_step(id=1, sequence=1)
    kitchen_step = make_product_step(id=2, sequence=1)
    tasks = [
        make_task_for_step(id=1, step=bar_step, status="NEW"),
        make_task_for_step(id=2, step=kitchen_step, status="NEW"),
    ]
    db = FakeKitchenSession(tasks)
    events: list[tuple[str, int]] = []

    async def broadcast(*, event: str, task: KitchenTask) -> None:
        events.append((event, task.id))

    monkeypatch.setattr(kitchen_service, "_broadcast_task_event", broadcast)

    asyncio.run(
        kitchen_service.start_task(
            cast(AsyncSession, db),
            task=tasks[0],
            allow_new=True,
            start_section_id=bar_step.kitchen_section_id,
        )
    )

    assert tasks[0].status == "IN_PROGRESS"
    assert tasks[1].status == "NEW"
    assert db.commits == 1
    assert events == [("kitchen_task_started", 1)]


def test_kitchen_task_complete_starts_ready_dependent_step(monkeypatch):
    parent_step = make_product_step(id=1, sequence=1)
    child_step = make_product_step(id=2, sequence=2, depends_on_sequence=1)
    tasks = [
        make_task_for_step(id=1, step=parent_step, status="IN_PROGRESS"),
        make_task_for_step(id=2, step=child_step),
    ]
    db = FakeKitchenSession(tasks)
    events: list[tuple[str, int]] = []

    async def broadcast(*, event: str, task: KitchenTask) -> None:
        events.append((event, task.id))

    monkeypatch.setattr(kitchen_service, "_broadcast_task_event", broadcast)

    asyncio.run(kitchen_service.complete_task(cast(AsyncSession, db), task=tasks[0]))

    assert tasks[0].status == "COMPLETED"
    assert tasks[1].status == "IN_PROGRESS"
    assert db.commits == 1
    assert events == [
        ("kitchen_task_completed", 1),
        ("kitchen_task_started", 2),
    ]


def test_bartender_completion_starts_new_dependent_bar_step(monkeypatch):
    first_step = make_product_step(id=7, sequence=1)
    second_step = make_product_step(id=8, sequence=2, depends_on_sequence=1)
    first_step.kitchen_section_id = 7
    second_step.kitchen_section_id = 7
    tasks = [
        make_task_for_step(id=1, step=first_step, status="IN_PROGRESS"),
        make_task_for_step(id=2, step=second_step, status="NEW"),
    ]
    db = FakeKitchenSession(tasks)
    events: list[tuple[str, int]] = []

    async def broadcast(*, event: str, task: KitchenTask) -> None:
        events.append((event, task.id))

    monkeypatch.setattr(kitchen_service, "_broadcast_task_event", broadcast)

    asyncio.run(
        kitchen_service.complete_task(
            cast(AsyncSession, db),
            task=tasks[0],
            allow_new_following=True,
            start_section_id=7,
        )
    )

    assert tasks[0].status == "COMPLETED"
    assert tasks[1].status == "IN_PROGRESS"
    assert db.commits == 1
    assert events == [
        ("kitchen_task_completed", 1),
        ("kitchen_task_started", 2),
    ]


def test_kitchen_task_complete_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        task = make_kitchen_task()
        task.status = "IN_PROGRESS"
        task.started_at = datetime.now(timezone.utc)
        return task

    async def complete_task(
        _db,
        *,
        task,
        allow_new_following=False,
        start_section_id=None,
    ):
        assert allow_new_following is False
        assert start_section_id is None
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


def test_bar_ready_event_waits_for_every_bar_task(monkeypatch):
    completed_bar_task = make_kitchen_task()
    completed_bar_task.id = 1
    completed_bar_task.kitchen_section_id = 7
    completed_bar_task.status = "COMPLETED"

    pending_bar_task = make_kitchen_task()
    pending_bar_task.id = 2
    pending_bar_task.order_item_id = 2
    pending_bar_task.kitchen_section_id = 7
    pending_bar_task.status = "IN_PROGRESS"

    order = SimpleNamespace(
        id=10,
        status="OPEN",
        table_id=3,
        table=SimpleNamespace(table_number="11"),
        waiter_id=5,
        items=[
            SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[completed_bar_task]),
            SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[pending_bar_task]),
        ],
    )
    db = FakeReadySession()
    events: list[dict[str, Any]] = []

    async def load_order_for_task(_db, *, order_item_id: int):
        assert order_item_id == 1
        return order

    async def broadcast_many(*, channels, event, data):
        events.append({"channels": channels, "event": event, "data": data})

    monkeypatch.setattr(kitchen_service, "_load_order_for_task", load_order_for_task)
    monkeypatch.setattr(websocket_manager, "broadcast_many", broadcast_many)

    ready = asyncio.run(
        kitchen_service.broadcast_section_ready_if_complete(
            cast(AsyncSession, db),
            task=completed_bar_task,
            section_id=7,
            event="bar_order_ready",
            department="BAR",
            channels=["waiters", "bar"],
        )
    )

    assert ready is False
    assert events == []
    assert db.commits == 0


def test_bar_ready_event_ignores_unfinished_kitchen_tasks(monkeypatch):
    first_bar_task = make_kitchen_task()
    first_bar_task.id = 1
    first_bar_task.kitchen_section_id = 7
    first_bar_task.status = "COMPLETED"

    second_bar_task = make_kitchen_task()
    second_bar_task.id = 2
    second_bar_task.order_item_id = 2
    second_bar_task.kitchen_section_id = 7
    second_bar_task.status = "COMPLETED"

    kitchen_task = make_kitchen_task()
    kitchen_task.id = 3
    kitchen_task.order_item_id = 3
    kitchen_task.kitchen_section_id = 2
    kitchen_task.status = "IN_PROGRESS"

    bar_item_one = SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[first_bar_task])
    bar_item_two = SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[second_bar_task])
    kitchen_item = SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[kitchen_task])
    order = SimpleNamespace(
        id=10,
        status="OPEN",
        table_id=3,
        table=SimpleNamespace(table_number="11"),
        waiter_id=5,
        items=[bar_item_one, bar_item_two, kitchen_item],
    )
    db = FakeReadySession()
    events: list[dict[str, Any]] = []

    async def load_order_for_task(_db, *, order_item_id: int):
        assert order_item_id == 1
        return order

    async def broadcast_many(*, channels, event, data):
        events.append({"channels": channels, "event": event, "data": data})

    monkeypatch.setattr(kitchen_service, "_load_order_for_task", load_order_for_task)
    monkeypatch.setattr(websocket_manager, "broadcast_many", broadcast_many)

    ready = asyncio.run(
        kitchen_service.broadcast_section_ready_if_complete(
            cast(AsyncSession, db),
            task=first_bar_task,
            section_id=7,
            event="bar_order_ready",
            department="BAR",
            channels=["waiters", "bar"],
        )
    )

    assert ready is True
    assert bar_item_one.status == "READY"
    assert bar_item_two.status == "READY"
    assert kitchen_item.status == "IN_PROGRESS"
    assert db.commits == 1
    assert events == [
        {
                "channels": ["waiters", "bar", "public_qr"],
                "event": "bar_order_ready",
                "data": {
                    "order_id": 10,
                    "table_id": 3,
                    "table_number": "11",
                    "waiter_id": 5,
                    "department": "BAR",
                    "public_status": "READY",
                },
            }
        ]


def test_bartender_completion_checks_bar_order_readiness(monkeypatch):
    task = make_kitchen_task()
    task.kitchen_section_id = 1
    task.status = "IN_PROGRESS"
    readiness_checks: list[dict[str, Any]] = []

    async def get(_db, id: int):
        assert id == 1
        return task

    async def complete_task(
        _db,
        *,
        task,
        allow_new_following=False,
        start_section_id=None,
    ):
        assert allow_new_following is True
        assert start_section_id == 1
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        return task

    async def get_bar_section_id(_db):
        return 1

    async def broadcast_section_ready_if_complete(_db, **kwargs):
        readiness_checks.append(kwargs)
        return True

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    monkeypatch.setattr(kitchen_service, "complete_task", complete_task)
    monkeypatch.setattr(
        kitchen_service,
        "broadcast_section_ready_if_complete",
        broadcast_section_ready_if_complete,
    )
    monkeypatch.setattr(kitchen_routes, "_get_bar_section_id", get_bar_section_id)
    override_current_user("BARTENDER")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/complete",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert readiness_checks == [
        {
            "task": task,
            "section_id": 1,
            "event": "bar_order_ready",
            "department": "BAR",
            "channels": ["waiters", "bar"],
        }
    ]


def test_completed_bar_task_does_not_repeat_ready_event(monkeypatch):
    task = make_kitchen_task()
    task.kitchen_section_id = 1
    task.status = "COMPLETED"
    task.completed_at = datetime.now(timezone.utc)
    readiness_checks: list[dict[str, Any]] = []

    async def get(_db, id: int):
        assert id == 1
        return task

    async def complete_task(
        _db,
        *,
        task,
        allow_new_following=False,
        start_section_id=None,
    ):
        assert allow_new_following is True
        assert start_section_id == 1
        return task

    async def get_bar_section_id(_db):
        return 1

    async def broadcast_section_ready_if_complete(_db, **kwargs):
        readiness_checks.append(kwargs)
        return True

    monkeypatch.setattr(crud_kitchen_task, "get", get)
    monkeypatch.setattr(kitchen_service, "complete_task", complete_task)
    monkeypatch.setattr(
        kitchen_service,
        "broadcast_section_ready_if_complete",
        broadcast_section_ready_if_complete,
    )
    monkeypatch.setattr(kitchen_routes, "_get_bar_section_id", get_bar_section_id)
    override_current_user("BARTENDER")

    try:
        response = client.post(
            "/api/v1/kitchen-tasks/1/complete",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert readiness_checks == []


def test_kitchen_ready_event_does_not_wait_for_bar(monkeypatch):
    kitchen_task = make_kitchen_task()
    kitchen_task.id = 1
    kitchen_task.kitchen_section_id = 2
    kitchen_task.status = "COMPLETED"

    bar_task = make_kitchen_task()
    bar_task.id = 2
    bar_task.order_item_id = 2
    bar_task.kitchen_section_id = 7
    bar_task.status = "IN_PROGRESS"

    kitchen_item = SimpleNamespace(status="PENDING", kitchen_tasks=[kitchen_task])
    bar_item = SimpleNamespace(status="IN_PROGRESS", kitchen_tasks=[bar_task])
    order = SimpleNamespace(
        id=10,
        table_id=3,
        waiter_id=5,
        items=[kitchen_item, bar_item],
    )
    db = FakeCompleteOrderSession(
        order=order,
        tasks=[kitchen_task, bar_task],
    )
    events: list[dict[str, Any]] = []

    async def get_bar_section_id(_db):
        return 7

    async def get_table(_db, id: int):
        assert id == 3
        return SimpleNamespace(table_number="11")

    async def broadcast_many(*, channels, event, data):
        events.append({"channels": channels, "event": event, "data": data})

    monkeypatch.setattr(kitchen_routes, "_get_bar_section_id", get_bar_section_id)
    monkeypatch.setattr(crud_restaurant_table, "get", get_table)
    monkeypatch.setattr(websocket_manager, "broadcast_many", broadcast_many)

    response = asyncio.run(
        kitchen_routes.complete_kitchen_order(
            10,
            cast(Any, db),
            make_user("WYDAWKA"),
        )
    )

    assert response == {"success": True}
    assert kitchen_item.status == "READY"
    assert bar_item.status == "IN_PROGRESS"
    assert events == [
        {
                "channels": ["waiters", "kitchen", "bar", "floor", "public_qr"],
                "event": "kitchen_order_ready",
                "data": {
                    "order_id": 10,
                    "table_id": 3,
                    "table_number": "11",
                    "waiter_id": 5,
                    "department": "KITCHEN",
                    "public_status": "READY",
                },
            }
        ]


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


def test_list_current_user_closed_payments_reaches_service(monkeypatch):
    closed_order = make_order()
    closed_order.status = "CLOSED"
    closed_order.closed_at = datetime.now(timezone.utc)

    async def list_closed_payments_for_user(_db, *, user_id: int):
        assert user_id == 1
        return [(make_payment(), closed_order)]

    monkeypatch.setattr(
        payment_service,
        "list_closed_payments_for_user",
        list_closed_payments_for_user,
    )
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/payments/current-user/closed",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["order_id"] == 1
    assert response.json()[0]["method"] == "CARD"


def test_toggle_payment_method_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_payment()

    async def toggle_payment_method(
        _db,
        *,
        payment,
        user_id: int,
        authorized_user_id: int,
        can_manage_all: bool,
        reason: str,
    ):
        assert payment.id == 1
        assert user_id == 1
        assert authorized_user_id == 1
        assert can_manage_all is True
        assert reason == "Correction"
        payment.method = "CASH"
        return payment

    monkeypatch.setattr(crud_payment, "get", get)
    monkeypatch.setattr(payment_service, "toggle_payment_method", toggle_payment_method)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/payments/1/toggle-method",
            headers={"Authorization": "Bearer fake-token"},
            json={"reason": "Correction"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["method"] == "CASH"


def test_payment_register_with_close_order_uses_order_close(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.added: list[Any] = []
            self.refreshed: list[Any] = []

        def add(self, obj: Any):
            self.added.append(obj)

        async def execute(self, _query):
            class Result:
                def scalar_one(self):
                    return Decimal("0.00")

            return Result()

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
