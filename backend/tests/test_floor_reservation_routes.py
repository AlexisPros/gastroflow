from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import floor_plan as crud_floor_plan
from app.crud import floor_plan_table as crud_floor_plan_table
from app.crud import reservation as crud_reservation
from app.crud import reservation_table as crud_reservation_table
from app.crud import restaurant_table as crud_restaurant_table
from app.main import app
from app.models.floor_plan import FloorPlan
from app.models.floor_plan_table import FloorPlanTable
from app.models.reservation import Reservation
from app.models.reservation_table import ReservationTable
from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.services import floor_plan_service, reservation_service


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


def make_floor_plan() -> FloorPlan:
    return FloorPlan(
        id=1,
        name="Main hall",
        width=1200,
        height=800,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def make_floor_plan_table() -> FloorPlanTable:
    return FloorPlanTable(
        id=1,
        floor_plan_id=1,
        table_id=1,
        x=Decimal("10.00"),
        y=Decimal("20.00"),
        width=Decimal("100.00"),
        height=Decimal("80.00"),
        rotation=Decimal("0.00"),
        shape="RECTANGLE",
    )


def make_restaurant_table() -> RestaurantTable:
    return RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="FREE",
        qr_code_url=None,
        is_active=True,
    )


def make_reservation() -> Reservation:
    return Reservation(
        id=1,
        table_id=1,
        customer_name="Jan Kowalski",
        customer_phone="+48123123123",
        guest_count=4,
        reservation_time=datetime(2026, 5, 26, 19, 0, tzinfo=timezone.utc),
        status="PENDING",
        notes=None,
        created_at=datetime.now(timezone.utc),
    )


def make_reservation_table() -> ReservationTable:
    return ReservationTable(
        id=1,
        reservation_id=1,
        table_id=1,
    )


def test_floor_plan_route_forbidden_for_waiter():
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/floor-plans/active",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_get_active_floor_plan_reaches_crud(monkeypatch):
    async def get_active(_db):
        return make_floor_plan()

    monkeypatch.setattr(crud_floor_plan, "get_active", get_active)
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/floor-plans/active",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Main hall"


def test_activate_floor_plan_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_floor_plan()

    async def activate(_db, *, floor_plan):
        assert floor_plan.id == 1
        floor_plan.is_active = True
        return floor_plan

    monkeypatch.setattr(crud_floor_plan, "get", get)
    monkeypatch.setattr(floor_plan_service, "activate", activate)
    override_current_user("ADMIN")

    try:
        response = client.post(
            "/api/v1/floor-plans/1/activate",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_add_table_to_floor_plan_reaches_service(monkeypatch):
    async def get_floor_plan(_db, id: int):
        assert id == 1
        return make_floor_plan()

    async def get_restaurant_table(_db, id: int):
        assert id == 1
        return make_restaurant_table()

    async def add_table(_db, *, floor_plan, table_id, position):
        assert floor_plan.id == 1
        assert table_id == 1
        assert position.x == Decimal("10.00")
        return make_floor_plan_table()

    monkeypatch.setattr(crud_floor_plan, "get", get_floor_plan)
    monkeypatch.setattr(crud_restaurant_table, "get", get_restaurant_table)
    monkeypatch.setattr(floor_plan_service, "add_table", add_table)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/floor-plans/1/tables",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "table_id": 1,
                "position": {
                    "x": "10.00",
                    "y": "20.00",
                    "width": "100.00",
                    "height": "80.00",
                    "rotation": "0.00",
                    "shape": "RECTANGLE",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["table_id"] == 1


def test_update_floor_plan_table_position_reaches_service(monkeypatch):
    async def get_floor_plan(_db, id: int):
        assert id == 1
        return make_floor_plan()

    async def get_floor_plan_table(_db, id: int):
        assert id == 1
        return make_floor_plan_table()

    async def update_table_position(_db, *, floor_plan, floor_plan_table, position):
        assert floor_plan.id == 1
        assert floor_plan_table.id == 1
        floor_plan_table.x = position.x
        floor_plan_table.y = position.y
        return floor_plan_table

    monkeypatch.setattr(crud_floor_plan, "get", get_floor_plan)
    monkeypatch.setattr(crud_floor_plan_table, "get", get_floor_plan_table)
    monkeypatch.setattr(
        floor_plan_service,
        "update_table_position",
        update_table_position,
    )
    override_current_user("MANAGER")

    try:
        response = client.patch(
            "/api/v1/floor-plans/1/tables/1/position",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "x": "30.00",
                "y": "40.00",
                "width": "100.00",
                "height": "80.00",
                "rotation": "0.00",
                "shape": "RECTANGLE",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["x"] == "30.00"
    assert response.json()["y"] == "40.00"


def test_remove_table_from_floor_plan_reaches_service(monkeypatch):
    async def get_floor_plan(_db, id: int):
        assert id == 1
        return make_floor_plan()

    async def get_floor_plan_table(_db, id: int):
        assert id == 1
        return make_floor_plan_table()

    async def remove_table(_db, *, floor_plan_table):
        assert floor_plan_table.id == 1
        return floor_plan_table

    monkeypatch.setattr(crud_floor_plan, "get", get_floor_plan)
    monkeypatch.setattr(crud_floor_plan_table, "get", get_floor_plan_table)
    monkeypatch.setattr(floor_plan_service, "remove_table", remove_table)
    override_current_user("MANAGER")

    try:
        response = client.delete(
            "/api/v1/floor-plans/1/tables/1",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_reservation_route_forbidden_for_kitchen_role():
    override_current_user("KITCHEN")

    try:
        response = client.post(
            "/api/v1/reservations/1/confirm",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_confirm_reservation_reaches_service(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_reservation()

    async def confirm(_db, *, reservation):
        assert reservation.id == 1
        reservation.status = "CONFIRMED"
        return reservation

    monkeypatch.setattr(crud_reservation, "get", get)
    monkeypatch.setattr(reservation_service, "confirm", confirm)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/reservations/1/confirm",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED"


def test_assign_reservation_tables_reaches_service(monkeypatch):
    async def get_reservation(_db, id: int):
        assert id == 1
        return make_reservation()

    async def get_table(_db, id: int):
        assert id in {1, 2}
        table = make_restaurant_table()
        table.id = id
        return table

    async def assign_tables(_db, *, reservation, table_ids):
        assert reservation.id == 1
        assert table_ids == [1, 2]
        reservation.table_id = table_ids[0]
        return reservation

    monkeypatch.setattr(crud_reservation, "get", get_reservation)
    monkeypatch.setattr(crud_restaurant_table, "get", get_table)
    monkeypatch.setattr(reservation_service, "assign_tables", assign_tables)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/reservations/1/tables",
            headers={"Authorization": "Bearer fake-token"},
            json={"table_ids": [1, 2]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["table_id"] == 1


def test_list_reservation_tables_reaches_crud(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_reservation()

    async def get_by_reservation(_db, *, reservation_id: int):
        assert reservation_id == 1
        return [make_reservation_table()]

    monkeypatch.setattr(crud_reservation, "get", get)
    monkeypatch.setattr(
        crud_reservation_table,
        "get_by_reservation",
        get_by_reservation,
    )
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/reservations/1/tables",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["reservation_id"] == 1


def test_search_reservations_by_table_reaches_service(monkeypatch):
    async def find_table_reservations(_db, *, table_id, reservation_time):
        assert table_id == 1
        assert reservation_time == datetime(2026, 5, 26, 19, 0, tzinfo=timezone.utc)
        return [make_reservation()]

    monkeypatch.setattr(
        reservation_service,
        "find_table_reservations",
        find_table_reservations,
    )
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/reservations/search/by-table",
            headers={"Authorization": "Bearer fake-token"},
            params={
                "table_id": 1,
                "reservation_time": "2026-05-26T19:00:00Z",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["customer_name"] == "Jan Kowalski"
