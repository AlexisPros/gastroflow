from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.crud import employee_shift_report as crud_employee_shift_report
from app.main import app
from app.models.employee_shift import EmployeeShift
from app.models.employee_shift_report import EmployeeShiftReport
from app.models.user import User
from app.services import shift_service


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


def make_shift(status: str = "OPEN") -> EmployeeShift:
    return EmployeeShift(
        id=1,
        user_id=1,
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        status=status,
        opening_note="Start",
        closing_note=None,
    )


def make_report() -> EmployeeShiftReport:
    return EmployeeShiftReport(
        id=1,
        shift_id=1,
        user_id=1,
        orders_count=2,
        items_count=4,
        total_sales=Decimal("100.00"),
        total_tips=Decimal("12.00"),
        total_discounts=Decimal("8.00"),
        cash_total=Decimal("40.00"),
        card_total=Decimal("60.00"),
        other_payment_total=Decimal("0.00"),
        report_data={
            "sold_items": [],
            "discounts": [],
            "payment_methods": [],
        },
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(role: str = "WAITER") -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def test_start_shift_reaches_service(monkeypatch):
    async def start_shift(_db, *, user, opening_note):
        assert user.id == 1
        assert opening_note == "Morning shift"
        return make_shift()

    monkeypatch.setattr(shift_service, "start_shift", start_shift)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/shifts/start",
            headers={"Authorization": "Bearer fake-token"},
            json={"opening_note": "Morning shift"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"


def test_get_current_shift_returns_null_without_open_shift(monkeypatch):
    async def get_current_shift(_db, *, user):
        assert user.id == 1
        return None

    monkeypatch.setattr(shift_service, "get_current_shift", get_current_shift)
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/shifts/current",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() is None


def test_close_current_shift_returns_report(monkeypatch):
    async def close_current_shift(_db, *, user, closing_note):
        assert user.id == 1
        assert closing_note == "Done"
        return make_report()

    monkeypatch.setattr(shift_service, "close_current_shift", close_current_shift)
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/shifts/current/close",
            headers={"Authorization": "Bearer fake-token"},
            json={"closing_note": "Done"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["orders_count"] == 2
    assert response.json()["total_sales"] == "100.00"


def test_list_shift_reports_requires_manager_role(monkeypatch):
    async def get_multi(_db, *, skip, limit):
        assert skip == 0
        assert limit == 100
        return [make_report()]

    monkeypatch.setattr(crud_employee_shift_report, "get_multi", get_multi)
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/shift-reports",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["total_discounts"] == "8.00"
