import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.models.ingredient import Ingredient
from app.models.order_item import OrderItem
from app.models.product_ingredient import ProductIngredient
from app.models.product_modifier import ProductModifier
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.models.warehouse_document import WarehouseDocument
from app.models.warehouse_document_item import WarehouseDocumentItem
from app.services.stock_service import InventoryConflictError, StockService


class ScalarListResult:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def scalars(self):
        return self

    def all(self) -> list[Any]:
        return self.values


class RequirementSession:
    def __init__(
        self,
        *,
        recipe: list[ProductIngredient],
        modifiers: list[ProductModifier],
    ) -> None:
        self.results = [ScalarListResult(recipe), ScalarListResult(modifiers)]

    async def execute(self, _statement: Any) -> ScalarListResult:
        return self.results.pop(0)


class InventorySession:
    def __init__(self, stock_items: list[StockItem]) -> None:
        self.stock_items = stock_items
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, _statement: Any) -> ScalarListResult:
        return ScalarListResult(self.stock_items)

    def add(self, item: Any) -> None:
        self.added.append(item)

    def add_all(self, items: list[Any]) -> None:
        self.added.extend(items)

    async def commit(self) -> None:
        self.committed = True


def test_modifier_replaces_recipe_ingredient_in_stock_requirements() -> None:
    service = StockService()
    order_item = OrderItem(id=1, order_id=1, product_id=10, quantity=2)
    session = RequirementSession(
        recipe=[
            ProductIngredient(product_id=10, ingredient_id=1, quantity=Decimal("0.200")),
            ProductIngredient(product_id=10, ingredient_id=2, quantity=Decimal("0.100")),
        ],
        modifiers=[
            ProductModifier(
                product_id=10,
                modifier_id=5,
                stock_ingredient_id=3,
                stock_quantity=Decimal("0.150"),
                replaces_ingredient_id=1,
            ),
        ],
    )

    requirements = asyncio.run(
        service._build_stock_requirements(  # noqa: SLF001
            session,  # type: ignore[arg-type]
            order_item=order_item,
        ),
    )

    assert 1 not in requirements
    assert requirements[2] == Decimal("0.200")
    assert requirements[3] == Decimal("0.300")


def test_bottle_modifier_replaces_wine_measured_in_millilitres() -> None:
    service = StockService()
    order_item = OrderItem(id=2, order_id=1, product_id=20, quantity=2)
    session = RequirementSession(
        recipe=[
            ProductIngredient(product_id=20, ingredient_id=4, quantity=Decimal("150.000")),
        ],
        modifiers=[
            ProductModifier(
                product_id=20,
                modifier_id=6,
                stock_ingredient_id=5,
                stock_quantity=Decimal("1.000"),
                replaces_ingredient_id=4,
            ),
        ],
    )

    requirements = asyncio.run(
        service._build_stock_requirements(  # noqa: SLF001
            session,  # type: ignore[arg-type]
            order_item=order_item,
        ),
    )

    assert 4 not in requirements
    assert requirements[5] == Decimal("2.000")


def test_document_lines_reject_duplicate_ingredients() -> None:
    with pytest.raises(ValueError, match="only once"):
        StockService._validate_lines(  # noqa: SLF001
            [
                (1, Decimal("1.000"), None),
                (1, Decimal("2.000"), None),
            ],
        )


def test_consumed_order_item_is_not_deducted_twice(monkeypatch) -> None:
    service = StockService()
    warehouse = Warehouse(id=1, name="Main", type="GENERAL", is_active=True, is_default=True)
    order_item = OrderItem(
        id=3,
        order_id=1,
        product_id=10,
        quantity=1,
        stock_consumed_at=object(),  # type: ignore[arg-type]
    )

    class Result:
        def scalar_one_or_none(self):
            return order_item

    class Session:
        async def execute(self, _statement: Any) -> Result:
            return Result()

    async def get_default(_db):
        return warehouse

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Stock consumption must not run twice")

    monkeypatch.setattr(service, "_get_default_warehouse", get_default)
    monkeypatch.setattr(service, "_consume_order_item", fail_if_called)

    movements = asyncio.run(
        service.consume_order_item_stock(  # type: ignore[arg-type]
            Session(),
            order_item_id=order_item.id,
        ),
    )

    assert movements == []


def test_inventory_records_differences_and_adjusts_stock(monkeypatch) -> None:
    service = StockService()
    warehouse = Warehouse(id=1, name="Main", type="GENERAL", is_active=True, is_default=True)
    flour = Ingredient(id=1, name="Mąka", unit="kg", is_active=True)
    oil = Ingredient(id=2, name="Olej", unit="l", is_active=True)
    flour_stock = StockItem(
        id=10,
        warehouse_id=warehouse.id,
        ingredient_id=flour.id,
        quantity=Decimal("10.000"),
        minimum_quantity=None,
        is_active=True,
    )
    oil_stock = StockItem(
        id=11,
        warehouse_id=warehouse.id,
        ingredient_id=oil.id,
        quantity=Decimal("2.000"),
        minimum_quantity=None,
        is_active=True,
    )
    flour_stock.ingredient = flour
    oil_stock.ingredient = oil
    session = InventorySession([flour_stock, oil_stock])
    document = WarehouseDocument(
        id=50,
        document_number="INW/2026/000050",
        document_type="INW",
        status="COMPLETED",
        source_warehouse_id=warehouse.id,
        operation_date=date(2026, 6, 30),
    )

    async def get_warehouse(_db: Any, _warehouse_id: int) -> Warehouse:
        return warehouse

    async def create_document(_db: Any, **_kwargs: Any) -> WarehouseDocument:
        return document

    async def reload_document(_db: Any, _document_id: int) -> WarehouseDocument:
        return document

    monkeypatch.setattr(service, "_get_active_warehouse", get_warehouse)
    monkeypatch.setattr(service, "_create_document", create_document)
    monkeypatch.setattr(service, "_reload_document", reload_document)

    result = asyncio.run(
        service.inventory_stock(  # type: ignore[arg-type]
            session,
            warehouse_id=warehouse.id,
            lines=[
                (flour_stock.id, Decimal("10.000"), Decimal("8.000"), Decimal("3.00")),
                (oil_stock.id, Decimal("2.000"), Decimal("4.000"), Decimal("1.50")),
            ],
            issued_by_user_id=1,
            operation_date=date(2026, 6, 30),
            reason="Inwentaryzacja okresowa",
        ),
    )

    document_items = [item for item in session.added if isinstance(item, WarehouseDocumentItem)]
    movements = [item for item in session.added if isinstance(item, StockMovement)]
    assert result is document
    assert session.committed is True
    assert flour_stock.quantity == Decimal("8.000")
    assert oil_stock.quantity == Decimal("4.000")
    assert [(item.difference_quantity, item.difference_value) for item in document_items] == [
        (Decimal("-2.000"), Decimal("-6.00")),
        (Decimal("2.000"), Decimal("3.00")),
    ]
    assert [(movement.type, movement.quantity) for movement in movements] == [
        ("INVENTORY_LOSS", Decimal("2.000")),
        ("INVENTORY_GAIN", Decimal("2.000")),
    ]


def test_inventory_rejects_stale_book_quantity(monkeypatch) -> None:
    service = StockService()
    warehouse = Warehouse(id=1, name="Main", type="GENERAL", is_active=True, is_default=True)
    ingredient = Ingredient(id=1, name="Mąka", unit="kg", is_active=True)
    stock_item = StockItem(
        id=10,
        warehouse_id=warehouse.id,
        ingredient_id=ingredient.id,
        quantity=Decimal("9.000"),
        minimum_quantity=None,
        is_active=True,
    )
    stock_item.ingredient = ingredient
    session = InventorySession([stock_item])

    async def get_warehouse(_db: Any, _warehouse_id: int) -> Warehouse:
        return warehouse

    monkeypatch.setattr(service, "_get_active_warehouse", get_warehouse)

    with pytest.raises(InventoryConflictError, match="zmienił się"):
        asyncio.run(
            service.inventory_stock(  # type: ignore[arg-type]
                session,
                warehouse_id=warehouse.id,
                lines=[(stock_item.id, Decimal("10.000"), Decimal("8.000"), Decimal("3.00"))],
                issued_by_user_id=1,
                operation_date=date(2026, 6, 30),
                reason="Inwentaryzacja kontrolna",
            ),
        )

    assert session.committed is False
    assert stock_item.quantity == Decimal("9.000")
