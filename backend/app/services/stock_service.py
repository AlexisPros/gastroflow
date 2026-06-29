from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ingredient import Ingredient
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.product_ingredient import ProductIngredient
from app.models.product_modifier import ProductModifier
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.models.warehouse_document import WarehouseDocument
from app.models.warehouse_document_item import WarehouseDocumentItem


DocumentLine = tuple[int, Decimal, Decimal | None]


class StockService:
    async def apply_movement(
        self,
        db: AsyncSession,
        *,
        stock_item: StockItem,
        type: str,
        quantity_delta: Decimal,
        description: str | None = None,
        prevent_negative: bool = True,
    ) -> StockMovement:
        new_quantity = stock_item.quantity + quantity_delta
        if prevent_negative and new_quantity < 0:
            raise ValueError("Stock quantity cannot be negative.")

        stock_item.quantity = new_quantity
        movement = StockMovement(
            stock_item_id=stock_item.id,
            type=type,
            quantity=abs(quantity_delta),
            description=description,
        )
        db.add_all([stock_item, movement])
        await db.commit()
        await db.refresh(stock_item)
        await db.refresh(movement)
        return movement

    async def receive_stock(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        lines: list[DocumentLine],
        issued_by_user_id: int,
        operation_date: date,
        description: str | None = None,
    ) -> WarehouseDocument:
        self._validate_lines(lines)
        warehouse = await self._get_active_warehouse(db, warehouse_id)
        document = await self._create_document(
            db,
            document_type="PZ",
            destination_warehouse_id=warehouse.id,
            issued_by_user_id=issued_by_user_id,
            operation_date=operation_date,
            description=description,
        )

        for ingredient_id, quantity, unit_price in lines:
            ingredient = await self._get_ingredient(db, ingredient_id)
            stock_item = await self._get_or_create_stock_item(
                db,
                warehouse_id=warehouse.id,
                ingredient_id=ingredient.id,
            )
            stock_item.quantity += quantity
            self._add_document_line_and_movement(
                db,
                document=document,
                ingredient=ingredient,
                stock_item=stock_item,
                quantity=quantity,
                unit_price=unit_price,
                movement_type="PZ_IN",
            )

        await db.commit()
        return await self._reload_document(db, document.id)

    async def transfer_stock(
        self,
        db: AsyncSession,
        *,
        source_warehouse_id: int,
        destination_warehouse_id: int,
        lines: list[DocumentLine],
        issued_by_user_id: int,
        operation_date: date,
        description: str | None = None,
    ) -> WarehouseDocument:
        self._validate_lines(lines)
        if source_warehouse_id == destination_warehouse_id:
            raise ValueError("Source and destination warehouse must be different.")

        source = await self._get_active_warehouse(db, source_warehouse_id)
        destination = await self._get_active_warehouse(db, destination_warehouse_id)
        document = await self._create_document(
            db,
            document_type="MM",
            source_warehouse_id=source.id,
            destination_warehouse_id=destination.id,
            issued_by_user_id=issued_by_user_id,
            operation_date=operation_date,
            description=description,
        )

        for ingredient_id, quantity, unit_price in lines:
            ingredient = await self._get_ingredient(db, ingredient_id)
            source_item = await self._get_stock_item_for_update(
                db,
                warehouse_id=source.id,
                ingredient_id=ingredient.id,
            )
            if source_item is None or not source_item.is_active or source_item.quantity < quantity:
                raise ValueError(f"Not enough stock for {ingredient.name} in source warehouse.")
            destination_item = await self._get_or_create_stock_item(
                db,
                warehouse_id=destination.id,
                ingredient_id=ingredient.id,
            )

            source_item.quantity -= quantity
            destination_item.quantity += quantity
            line = self._add_document_item(
                db,
                document=document,
                ingredient=ingredient,
                quantity=quantity,
                unit_price=unit_price,
            )
            db.add_all(
                [
                    source_item,
                    destination_item,
                    line,
                    StockMovement(
                        stock_item_id=source_item.id,
                        warehouse_document_id=document.id,
                        type="MM_OUT",
                        quantity=quantity,
                        description=document.document_number,
                    ),
                    StockMovement(
                        stock_item_id=destination_item.id,
                        warehouse_document_id=document.id,
                        type="MM_IN",
                        quantity=quantity,
                        description=document.document_number,
                    ),
                ],
            )

        await db.commit()
        return await self._reload_document(db, document.id)

    async def write_off_stock(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        lines: list[DocumentLine],
        issued_by_user_id: int,
        operation_date: date,
        reason: str,
        description: str | None = None,
    ) -> WarehouseDocument:
        self._validate_lines(lines)
        if not reason.strip():
            raise ValueError("Write-off reason is required.")

        warehouse = await self._get_active_warehouse(db, warehouse_id)
        document = await self._create_document(
            db,
            document_type="RW",
            source_warehouse_id=warehouse.id,
            issued_by_user_id=issued_by_user_id,
            operation_date=operation_date,
            reason=reason.strip(),
            description=description,
        )

        for ingredient_id, quantity, unit_price in lines:
            ingredient = await self._get_ingredient(db, ingredient_id)
            stock_item = await self._get_stock_item_for_update(
                db,
                warehouse_id=warehouse.id,
                ingredient_id=ingredient.id,
            )
            if stock_item is None or not stock_item.is_active or stock_item.quantity < quantity:
                raise ValueError(f"Not enough stock to write off {ingredient.name}.")
            stock_item.quantity -= quantity
            self._add_document_line_and_movement(
                db,
                document=document,
                ingredient=ingredient,
                stock_item=stock_item,
                quantity=quantity,
                unit_price=unit_price,
                movement_type="RW_OUT",
            )

        await db.commit()
        return await self._reload_document(db, document.id)

    async def consume_order_stock(
        self,
        db: AsyncSession,
        *,
        order_id: int,
    ) -> list[StockMovement]:
        default_warehouse = await self._get_default_warehouse(db)

        result = await db.execute(
            select(OrderItem)
            .options(selectinload(OrderItem.product))
            .where(
                OrderItem.order_id == order_id,
                OrderItem.stock_consumed_at.is_(None),
            )
            .with_for_update(),
        )
        movements: list[StockMovement] = []
        for order_item in result.scalars().all():
            warehouse = None
            if order_item.product and order_item.product.warehouse_id:
                try:
                    warehouse = await self._get_active_warehouse(db, order_item.product.warehouse_id)
                except ValueError:
                    pass
            if warehouse is None:
                warehouse = default_warehouse
            if warehouse is None:
                continue

            movements.extend(
                await self._consume_order_item(
                    db,
                    order_item=order_item,
                    warehouse=warehouse,
                ),
            )
        return movements

    async def consume_order_item_stock(
        self,
        db: AsyncSession,
        *,
        order_item_id: int,
    ) -> list[StockMovement]:
        result = await db.execute(
            select(OrderItem)
            .options(selectinload(OrderItem.product))
            .where(OrderItem.id == order_item_id)
            .with_for_update(),
        )
        order_item = result.scalar_one_or_none()
        if order_item is None or order_item.stock_consumed_at is not None:
            return []

        warehouse = None
        if order_item.product and order_item.product.warehouse_id:
            try:
                warehouse = await self._get_active_warehouse(db, order_item.product.warehouse_id)
            except ValueError:
                pass
        if warehouse is None:
            warehouse = await self._get_default_warehouse(db)
        if warehouse is None:
            return []
        return await self._consume_order_item(db, order_item=order_item, warehouse=warehouse)

    async def consume_ingredients_for_order_item(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
        warehouse_id: int,
    ) -> list[StockMovement]:
        if order_item.stock_consumed_at is not None:
            return []
        warehouse = await self._get_active_warehouse(db, warehouse_id)
        movements = await self._consume_order_item(
            db,
            order_item=order_item,
            warehouse=warehouse,
        )
        await db.commit()
        return movements

    async def _consume_order_item(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
        warehouse: Warehouse,
    ) -> list[StockMovement]:
        requirements = await self._build_stock_requirements(db, order_item=order_item)
        order_item.stock_consumed_at = datetime.now(timezone.utc)
        db.add(order_item)
        if not requirements:
            return []

        document = await self._create_document(
            db,
            document_type="RW_AUTO",
            source_warehouse_id=warehouse.id,
            order_id=order_item.order_id,
            issued_by_user_id=None,
            operation_date=date.today(),
            reason="Automatyczne rozchód składników po przyjęciu zamówienia.",
            description=f"Order item #{order_item.id}",
        )
        movements: list[StockMovement] = []
        for ingredient_id, quantity in requirements.items():
            if quantity <= 0:
                continue
            ingredient = await self._get_ingredient(db, ingredient_id)
            stock_item = await self._get_or_create_stock_item(
                db,
                warehouse_id=warehouse.id,
                ingredient_id=ingredient.id,
            )
            stock_item.quantity -= quantity
            movement = StockMovement(
                stock_item_id=stock_item.id,
                warehouse_document_id=document.id,
                order_item_id=order_item.id,
                type="CONSUMPTION",
                quantity=quantity,
                description=f"Order item #{order_item.id}",
            )
            db.add_all(
                [
                    stock_item,
                    movement,
                    self._add_document_item(
                        db,
                        document=document,
                        ingredient=ingredient,
                        quantity=quantity,
                        unit_price=None,
                    ),
                ],
            )
            movements.append(movement)
        return movements

    async def _build_stock_requirements(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
    ) -> dict[int, Decimal]:
        result = await db.execute(
            select(ProductIngredient).where(ProductIngredient.product_id == order_item.product_id),
        )
        multiplier = Decimal(order_item.quantity)
        requirements = {
            item.ingredient_id: item.quantity * multiplier
            for item in result.scalars().all()
        }

        modifier_result = await db.execute(
            select(ProductModifier)
            .join(
                OrderItemModifier,
                OrderItemModifier.product_modifier_id == ProductModifier.id,
            )
            .where(OrderItemModifier.order_item_id == order_item.id),
        )
        for modifier in modifier_result.scalars().all():
            if modifier.replaces_ingredient_id is not None:
                requirements.pop(modifier.replaces_ingredient_id, None)
            if modifier.stock_ingredient_id is not None and modifier.stock_quantity is not None:
                requirements[modifier.stock_ingredient_id] = (
                    requirements.get(modifier.stock_ingredient_id, Decimal("0"))
                    + modifier.stock_quantity * multiplier
                )
        return requirements

    async def _create_document(
        self,
        db: AsyncSession,
        *,
        document_type: str,
        operation_date: date,
        source_warehouse_id: int | None = None,
        destination_warehouse_id: int | None = None,
        order_id: int | None = None,
        issued_by_user_id: int | None = None,
        reason: str | None = None,
        description: str | None = None,
    ) -> WarehouseDocument:
        document = WarehouseDocument(
            document_number=f"DRAFT-{uuid4().hex}",
            document_type=document_type,
            status="COMPLETED",
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            order_id=order_id,
            issued_by_user_id=issued_by_user_id,
            operation_date=operation_date,
            reason=reason,
            description=description,
        )
        db.add(document)
        await db.flush()
        document.document_number = f"{document_type}/{operation_date.year}/{document.id:06d}"
        db.add(document)
        await db.flush()
        return document

    def _add_document_line_and_movement(
        self,
        db: AsyncSession,
        *,
        document: WarehouseDocument,
        ingredient: Ingredient,
        stock_item: StockItem,
        quantity: Decimal,
        unit_price: Decimal | None,
        movement_type: str,
    ) -> None:
        db.add_all(
            [
                stock_item,
                self._add_document_item(
                    db,
                    document=document,
                    ingredient=ingredient,
                    quantity=quantity,
                    unit_price=unit_price,
                ),
                StockMovement(
                    stock_item_id=stock_item.id,
                    warehouse_document_id=document.id,
                    type=movement_type,
                    quantity=quantity,
                    description=document.document_number,
                ),
            ],
        )

    def _add_document_item(
        self,
        db: AsyncSession,
        *,
        document: WarehouseDocument,
        ingredient: Ingredient,
        quantity: Decimal,
        unit_price: Decimal | None,
    ) -> WarehouseDocumentItem:
        del db
        return WarehouseDocumentItem(
            warehouse_document_id=document.id,
            ingredient_id=ingredient.id,
            quantity=quantity,
            unit=ingredient.unit,
            unit_price=unit_price,
            total_value=quantity * unit_price if unit_price is not None else None,
        )

    async def _get_default_warehouse(self, db: AsyncSession) -> Warehouse | None:
        result = await db.execute(
            select(Warehouse)
            .where(Warehouse.is_active.is_(True), Warehouse.is_default.is_(True))
            .order_by(Warehouse.id)
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def _get_active_warehouse(self, db: AsyncSession, warehouse_id: int) -> Warehouse:
        result = await db.execute(
            select(Warehouse).where(
                Warehouse.id == warehouse_id,
                Warehouse.is_active.is_(True),
            ),
        )
        warehouse = result.scalar_one_or_none()
        if warehouse is None:
            raise ValueError("Warehouse does not exist or is inactive.")
        return warehouse

    async def _get_ingredient(self, db: AsyncSession, ingredient_id: int) -> Ingredient:
        ingredient = await db.get(Ingredient, ingredient_id)
        if ingredient is None:
            raise ValueError("Ingredient does not exist.")
        return ingredient

    async def _get_stock_item_for_update(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        ingredient_id: int,
    ) -> StockItem | None:
        result = await db.execute(
            select(StockItem)
            .where(
                StockItem.warehouse_id == warehouse_id,
                StockItem.ingredient_id == ingredient_id,
            )
            .with_for_update(),
        )
        return result.scalar_one_or_none()

    async def _get_or_create_stock_item(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        ingredient_id: int,
    ) -> StockItem:
        stock_item = await self._get_stock_item_for_update(
            db,
            warehouse_id=warehouse_id,
            ingredient_id=ingredient_id,
        )
        if stock_item is not None:
            if not stock_item.is_active:
                stock_item.is_active = True
                db.add(stock_item)
            return stock_item
        stock_item = StockItem(
            warehouse_id=warehouse_id,
            ingredient_id=ingredient_id,
            quantity=Decimal("0"),
            minimum_quantity=None,
        )
        db.add(stock_item)
        await db.flush()
        return stock_item

    async def _reload_document(self, db: AsyncSession, document_id: int) -> WarehouseDocument:
        result = await db.execute(
            select(WarehouseDocument)
            .where(WarehouseDocument.id == document_id)
            .options(
                selectinload(WarehouseDocument.items).selectinload(WarehouseDocumentItem.ingredient),
                selectinload(WarehouseDocument.source_warehouse),
                selectinload(WarehouseDocument.destination_warehouse),
                selectinload(WarehouseDocument.issued_by_user),
            ),
        )
        return result.scalar_one()

    @staticmethod
    def _validate_lines(lines: list[DocumentLine]) -> None:
        if not lines:
            raise ValueError("Document must contain at least one item.")
        if any(quantity <= 0 for _, quantity, _ in lines):
            raise ValueError("Document quantities must be greater than zero.")
        ingredient_ids = [ingredient_id for ingredient_id, _, _ in lines]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise ValueError("Each ingredient can appear only once in a document.")


stock_service = StockService()
