import asyncio
from decimal import Decimal
from typing import Any

import pytest

from app.models.order_item import OrderItem
from app.models.product_ingredient import ProductIngredient
from app.models.product_modifier import ProductModifier
from app.models.warehouse import Warehouse
from app.services.stock_service import StockService


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
