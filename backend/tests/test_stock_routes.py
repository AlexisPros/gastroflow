import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.routes import stock as stock_routes
from app.models.ingredient import Ingredient
from app.models.stock_item import StockItem
from app.models.user import User
from app.models.warehouse import Warehouse


class ScalarResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value


class RouteSession:
    def __init__(self, *, execute_values: list[Any] | None = None, item: StockItem | None = None) -> None:
        self.execute_values = list(execute_values or [])
        self.item = item
        self.committed = False

    async def execute(self, _statement: Any) -> ScalarResult:
        return ScalarResult(self.execute_values.pop(0))

    async def get(self, _model: Any, _object_id: int, **_kwargs: Any) -> StockItem | None:
        return self.item

    def add(self, _item: Any) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _item: Any) -> None:
        return None

    async def rollback(self) -> None:
        return None


def admin_user() -> User:
    return User(
        id=1,
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password_hash="hash",
        role="ADMIN",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_cannot_delete_warehouse_with_nonzero_stock(monkeypatch) -> None:
    warehouse = Warehouse(id=1, name="Główny", type="GENERAL", is_active=True, is_default=True)
    session = RouteSession(execute_values=[7])

    async def get_warehouse(_db: Any, _warehouse_id: int) -> Warehouse:
        return warehouse

    monkeypatch.setattr(stock_routes, "_get_warehouse_or_404", get_warehouse)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(stock_routes.delete_warehouse(1, session, admin_user()))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409
    assert warehouse.is_active is True
    assert session.committed is False


def test_deleting_empty_warehouse_keeps_history_by_deactivating_it(monkeypatch) -> None:
    warehouse = Warehouse(id=1, name="Główny", type="GENERAL", is_active=True, is_default=True)
    session = RouteSession(execute_values=[None, None])

    async def get_warehouse(_db: Any, _warehouse_id: int) -> Warehouse:
        return warehouse

    monkeypatch.setattr(stock_routes, "_get_warehouse_or_404", get_warehouse)

    result = asyncio.run(stock_routes.delete_warehouse(1, session, admin_user()))  # type: ignore[arg-type]

    assert result.is_active is False
    assert result.is_default is False
    assert session.committed is True


def test_cannot_delete_stock_item_with_nonzero_quantity(monkeypatch) -> None:
    ingredient = Ingredient(id=2, name="Ser", unit="kg", is_active=True)
    item = StockItem(
        id=3,
        warehouse_id=1,
        ingredient_id=ingredient.id,
        quantity=Decimal("1.000"),
        minimum_quantity=Decimal("0.500"),
        is_active=True,
    )
    item.ingredient = ingredient
    session = RouteSession(item=item)

    async def allow_access(_db: Any, _user: User, _warehouse_id: int) -> Warehouse:
        return Warehouse(id=1, name="Główny", type="GENERAL", is_active=True, is_default=True)

    monkeypatch.setattr(stock_routes, "_ensure_warehouse_access", allow_access)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(stock_routes.delete_warehouse_item(item.id, session, admin_user()))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409
    assert item.is_active is True


def test_zero_quantity_stock_item_is_soft_deleted(monkeypatch) -> None:
    ingredient = Ingredient(id=2, name="Ser", unit="kg", is_active=True)
    item = StockItem(
        id=3,
        warehouse_id=1,
        ingredient_id=ingredient.id,
        quantity=Decimal("0.000"),
        minimum_quantity=Decimal("0.500"),
        is_active=True,
    )
    item.ingredient = ingredient
    session = RouteSession(item=item)

    async def allow_access(_db: Any, _user: User, _warehouse_id: int) -> Warehouse:
        return Warehouse(id=1, name="Główny", type="GENERAL", is_active=True, is_default=True)

    monkeypatch.setattr(stock_routes, "_ensure_warehouse_access", allow_access)

    result = asyncio.run(
        stock_routes.delete_warehouse_item(item.id, session, admin_user()),  # type: ignore[arg-type]
    )

    assert result.is_active is False
    assert session.committed is True


def test_inventory_conflict_is_returned_as_http_409(monkeypatch) -> None:
    warehouse = Warehouse(id=1, name="Główny", type="GENERAL", is_active=True, is_default=True)
    session = RouteSession()

    async def allow_access(_db: Any, _user: User, _warehouse_id: int) -> Warehouse:
        return warehouse

    async def inventory_conflict(*_args: Any, **_kwargs: Any) -> None:
        raise stock_routes.InventoryConflictError("Stan towaru zmienił się.")

    monkeypatch.setattr(stock_routes, "_ensure_warehouse_access", allow_access)
    monkeypatch.setattr(stock_routes.stock_service, "inventory_stock", inventory_conflict)
    body = stock_routes.InventoryDocumentRequest(
        warehouse_id=warehouse.id,
        operation_date=date(2026, 6, 30),
        reason="Inwentaryzacja kontrolna",
        items=[
            stock_routes.InventoryLineInput(
                stock_item_id=3,
                book_quantity=Decimal("2.000"),
                actual_quantity=Decimal("1.500"),
                unit_price=Decimal("4.00"),
            ),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(stock_routes.create_inventory_document(body, session, admin_user()))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409
