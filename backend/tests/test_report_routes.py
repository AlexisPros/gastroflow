import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.kitchen_section import KitchenSection
from app.models.kitchen_task import KitchenTask
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas import DailyOperationsReport, DailyProductionReport, DailySalesReport
from app.services import report_service


client = TestClient(app)


def make_user(role: str = "MANAGER") -> User:
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


def override_current_user(role: str = "MANAGER") -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def make_sales_report() -> DailySalesReport:
    return DailySalesReport(
        report_date=date(2026, 5, 26),
        orders_count=2,
        items_count=4,
        total_sales=Decimal("120.00"),
        total_tips=Decimal("10.00"),
        total_discounts=Decimal("5.00"),
        cash_total=Decimal("40.00"),
        card_total=Decimal("80.00"),
        other_payment_total=Decimal("0.00"),
        sold_items=[],
        discounts=[],
        payment_methods=[],
    )


def make_production_report(scope: str) -> DailyProductionReport:
    return DailyProductionReport(
        report_date=date(2026, 5, 26),
        scope=scope,
        sections=[],
        tasks_count=3,
        completed_tasks_count=2,
        items_count=4,
        estimated_minutes=25,
        actual_minutes=20,
    )


def make_operations_report() -> DailyOperationsReport:
    return DailyOperationsReport(
        report_date=date(2026, 5, 26),
        sales=make_sales_report(),
        kitchen=make_production_report("KITCHEN"),
        bar=make_production_report("BAR"),
        production_total=make_production_report("ALL"),
    )


def test_daily_sales_report_reaches_service(monkeypatch):
    async def build_daily_sales_report(_db, *, report_date):
        assert report_date == date(2026, 5, 26)
        return make_sales_report()

    monkeypatch.setattr(
        report_service,
        "build_daily_sales_report",
        build_daily_sales_report,
    )
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/reports/sales/daily?report_date=2026-05-26",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total_sales"] == "120.00"


def test_daily_kitchen_report_reaches_service(monkeypatch):
    async def build_daily_production_report(_db, *, report_date, scope):
        assert report_date == date(2026, 5, 26)
        assert scope == "KITCHEN"
        return make_production_report(scope)

    monkeypatch.setattr(
        report_service,
        "build_daily_production_report",
        build_daily_production_report,
    )
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/reports/kitchen/daily?report_date=2026-05-26",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["scope"] == "KITCHEN"


def test_daily_bar_report_reaches_service(monkeypatch):
    async def build_daily_production_report(_db, *, report_date, scope):
        assert report_date == date(2026, 5, 26)
        assert scope == "BAR"
        return make_production_report(scope)

    monkeypatch.setattr(
        report_service,
        "build_daily_production_report",
        build_daily_production_report,
    )
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/reports/bar/daily?report_date=2026-05-26",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["scope"] == "BAR"


def test_daily_operations_report_reaches_service(monkeypatch):
    async def build_daily_operations_report(_db, *, report_date):
        assert report_date == date(2026, 5, 26)
        return make_operations_report()

    monkeypatch.setattr(
        report_service,
        "build_daily_operations_report",
        build_daily_operations_report,
    )
    override_current_user("ADMIN")

    try:
        response = client.get(
            "/api/v1/reports/operations/daily?report_date=2026-05-26",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["kitchen"]["scope"] == "KITCHEN"
    assert response.json()["bar"]["scope"] == "BAR"


def test_report_routes_forbid_waiter():
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/reports/sales/daily",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_daily_production_report_groups_task_rows(monkeypatch):
    section = KitchenSection(id=1, name="Hot Kitchen", is_active=True)
    product = Product(
        id=1,
        category_id=1,
        kitchen_section_id=1,
        name="Steak",
        description=None,
        price=Decimal("60.00"),
        preparation_time=20,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    order_item = OrderItem(
        id=1,
        order_id=1,
        product_id=1,
        quantity=2,
        unit_price=Decimal("60.00"),
        total_price=Decimal("120.00"),
        status="NEW",
        notes=None,
    )
    task = KitchenTask(
        id=1,
        order_item_id=1,
        kitchen_section_id=1,
        product_kitchen_step_id=None,
        assigned_user_id=None,
        status="COMPLETED",
        estimated_time=20,
        started_at=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 26, 12, 18, tzinfo=timezone.utc),
    )

    async def get_production_rows(_db, *, report_date, scope):
        assert report_date == date(2026, 5, 26)
        assert scope == "KITCHEN"
        return [(task, section, order_item, product)]

    monkeypatch.setattr(report_service, "_get_production_rows", get_production_rows)

    report = asyncio.run(
        report_service.build_daily_production_report(
            None,
            scope="KITCHEN",
            report_date=date(2026, 5, 26),
        ),
    )

    assert report.tasks_count == 1
    assert report.completed_tasks_count == 1
    assert report.items_count == 2
    assert report.estimated_minutes == 40
    assert report.actual_minutes == 18
    assert report.sections[0].sold_items[0].total == Decimal("120.00")
