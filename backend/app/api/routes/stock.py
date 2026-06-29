from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import ADMIN, CurrentUser, DbSession, STOCK_ROLES, get_or_404, raise_bad_request
from app.crud import order_item as crud_order_item
from app.crud import stock_item as crud_stock_item
from app.models.ingredient import Ingredient
from app.models.stock_item import StockItem
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.warehouse_document import WarehouseDocument
from app.models.warehouse_document_item import WarehouseDocumentItem
from app.models.warehouse_user_access import WarehouseUserAccess
from app.schemas import StockMovementRead
from app.schemas.stock_item import StockItemRead
from app.services import stock_service

router = APIRouter(tags=["Stock"])


class ApplyStockMovementRequest(BaseModel):
    type: str
    quantity_delta: Decimal
    description: str | None = None
    prevent_negative: bool = True


class ConsumeOrderItemStockRequest(BaseModel):
    warehouse_id: int


class WarehouseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_default: bool = False


class WarehouseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None
    is_default: bool | None = None


class WarehouseRead(BaseModel):
    id: int
    name: str
    type: str
    is_active: bool
    is_default: bool


class WarehouseAccessUpdateRequest(BaseModel):
    user_ids: list[int]


class WarehouseAccessUserRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    role: str
    is_active: bool
    has_access: bool


class IngredientOptionRead(BaseModel):
    id: int
    name: str
    unit: str
    is_active: bool


class StockItemDetailRead(BaseModel):
    id: int
    warehouse_id: int
    ingredient_id: int
    ingredient_name: str
    unit: str
    quantity: Decimal
    minimum_quantity: Decimal | None
    is_low_stock: bool
    is_active: bool


class StockItemCreateRequest(BaseModel):
    ingredient_id: int
    minimum_quantity: Decimal | None = Field(default=None, ge=Decimal("0"))


class StockItemThresholdRequest(BaseModel):
    minimum_quantity: Decimal | None = Field(default=None, ge=Decimal("0"))


class StockItemUpdateRequest(BaseModel):
    ingredient_name: str | None = Field(default=None, min_length=1, max_length=150)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    minimum_quantity: Decimal | None = Field(default=None, ge=Decimal("0"))


class DocumentLineInput(BaseModel):
    ingredient_id: int
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_price: Decimal | None = Field(default=None, ge=Decimal("0"))


class ReceiptDocumentRequest(BaseModel):
    warehouse_id: int
    operation_date: date
    description: str | None = Field(default=None, max_length=1000)
    items: list[DocumentLineInput] = Field(min_length=1)


class TransferDocumentRequest(BaseModel):
    source_warehouse_id: int
    destination_warehouse_id: int
    operation_date: date
    description: str | None = Field(default=None, max_length=1000)
    items: list[DocumentLineInput] = Field(min_length=1)


class WriteOffDocumentRequest(BaseModel):
    warehouse_id: int
    operation_date: date
    reason: str = Field(min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=1000)
    items: list[DocumentLineInput] = Field(min_length=1)


class WarehouseDocumentItemRead(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal | None
    total_value: Decimal | None


class WarehouseDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_number: str
    document_type: str
    status: str
    source_warehouse_id: int | None
    source_warehouse_name: str | None
    destination_warehouse_id: int | None
    destination_warehouse_name: str | None
    order_id: int | None
    issued_by_user_id: int | None
    issued_by_name: str | None
    operation_date: date
    issued_at: datetime
    reason: str | None
    description: str | None
    items: list[WarehouseDocumentItemRead]


@router.get("/stock/warehouses", response_model=list[WarehouseRead])
async def list_accessible_warehouses(db: DbSession, current_user: CurrentUser) -> list[Warehouse]:
    stmt = (
        select(Warehouse)
        .where(Warehouse.is_active.is_(True))
        .order_by(Warehouse.is_default.desc(), Warehouse.name)
    )
    if current_user.role != ADMIN:
        stmt = (
            stmt.join(WarehouseUserAccess)
            .where(WarehouseUserAccess.user_id == current_user.id)
        )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


@router.post(
    "/stock/warehouses",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_warehouse(
    body: WarehouseCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Warehouse:
    _require_admin(current_user)
    existing_count = len((await db.execute(select(Warehouse.id))).scalars().all())
    make_default = body.is_default or existing_count == 0
    if make_default:
        await db.execute(update(Warehouse).values(is_default=False))
    warehouse = Warehouse(
        name=body.name.strip(),
        type="GENERAL",
        is_active=True,
        is_default=make_default,
    )
    db.add(warehouse)
    await db.commit()
    await db.refresh(warehouse)
    return warehouse


@router.patch("/stock/warehouses/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: int,
    body: WarehouseUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Warehouse:
    _require_admin(current_user)
    warehouse = await _get_warehouse_or_404(db, warehouse_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        await db.execute(
            update(Warehouse)
            .where(Warehouse.id != warehouse_id)
            .values(is_default=False),
        )
    elif data.get("is_default") is False and warehouse.is_default:
        replacement = (
            await db.execute(
                select(Warehouse)
                .where(Warehouse.id != warehouse_id, Warehouse.is_active.is_(True))
                .order_by(Warehouse.id)
                .limit(1),
            )
        ).scalar_one_or_none()
        if replacement is None:
            data["is_default"] = True
        else:
            replacement.is_default = True
            db.add(replacement)
    for field, value in data.items():
        setattr(warehouse, field, value.strip() if isinstance(value, str) else value)
    if warehouse.is_default:
        warehouse.is_active = True
    db.add(warehouse)
    await db.commit()
    await db.refresh(warehouse)
    return warehouse


@router.delete("/stock/warehouses/{warehouse_id}", response_model=WarehouseRead)
async def delete_warehouse(
    warehouse_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Warehouse:
    _require_admin(current_user)
    warehouse = await _get_warehouse_or_404(db, warehouse_id)
    non_empty_item = (
        await db.execute(
            select(StockItem.id)
            .where(
                StockItem.warehouse_id == warehouse_id,
                StockItem.quantity != Decimal("0"),
            )
            .limit(1),
        )
    ).scalar_one_or_none()
    if non_empty_item is not None:
        raise HTTPException(
            status_code=409,
            detail="Nie można usunąć magazynu z niezerowym stanem. Najpierw przenieś lub odpisz wszystkie towary.",
        )

    warehouse.is_active = False
    warehouse.is_default = False
    db.add(warehouse)

    replacement = (
        await db.execute(
            select(Warehouse)
            .where(Warehouse.id != warehouse_id, Warehouse.is_active.is_(True))
            .order_by(Warehouse.id)
            .limit(1),
        )
    ).scalar_one_or_none()
    if replacement is not None:
        existing_default = (
            await db.execute(
                select(Warehouse.id).where(
                    Warehouse.id != warehouse_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.is_default.is_(True),
                ),
            )
        ).scalar_one_or_none()
        if existing_default is None:
            replacement.is_default = True
            db.add(replacement)

    await db.commit()
    await db.refresh(warehouse)
    return warehouse


@router.get(
    "/stock/warehouses/{warehouse_id}/access",
    response_model=list[WarehouseAccessUserRead],
)
async def list_warehouse_access(
    warehouse_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[WarehouseAccessUserRead]:
    _require_admin(current_user)
    await _get_warehouse_or_404(db, warehouse_id)
    access_ids = set(
        (
            await db.execute(
                select(WarehouseUserAccess.user_id).where(
                    WarehouseUserAccess.warehouse_id == warehouse_id,
                ),
            )
        ).scalars().all(),
    )
    users = list(
        (
            await db.execute(
                select(User).order_by(User.is_active.desc(), User.last_name, User.first_name),
            )
        ).scalars().all(),
    )
    return [
        WarehouseAccessUserRead(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            is_active=user.is_active,
            has_access=user.id in access_ids,
        )
        for user in users
    ]


@router.put(
    "/stock/warehouses/{warehouse_id}/access",
    response_model=list[WarehouseAccessUserRead],
)
async def update_warehouse_access(
    warehouse_id: int,
    body: WarehouseAccessUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[WarehouseAccessUserRead]:
    _require_admin(current_user)
    await _get_warehouse_or_404(db, warehouse_id)
    user_ids = set(body.user_ids)
    if user_ids:
        existing_ids = set(
            (
                await db.execute(
                    select(User.id).where(User.id.in_(user_ids), User.is_active.is_(True)),
                )
            ).scalars().all(),
        )
        if existing_ids != user_ids:
            raise HTTPException(status_code=400, detail="One or more workers do not exist or are inactive.")
    await db.execute(
        delete(WarehouseUserAccess).where(WarehouseUserAccess.warehouse_id == warehouse_id),
    )
    db.add_all(
        [WarehouseUserAccess(warehouse_id=warehouse_id, user_id=user_id) for user_id in user_ids],
    )
    await db.commit()
    return await list_warehouse_access(warehouse_id, db, current_user)


@router.get("/stock/ingredients", response_model=list[IngredientOptionRead])
async def list_stock_ingredients(db: DbSession, current_user: CurrentUser) -> list[Ingredient]:
    await _ensure_any_warehouse_access(db, current_user)
    result = await db.execute(select(Ingredient).order_by(Ingredient.name))
    return list(result.scalars().all())


@router.get(
    "/stock/warehouses/{warehouse_id}/items",
    response_model=list[StockItemDetailRead],
)
async def list_warehouse_items(
    warehouse_id: int,
    db: DbSession,
    current_user: CurrentUser,
    low_only: bool = Query(default=False),
) -> list[StockItemDetailRead]:
    await _ensure_warehouse_access(db, current_user, warehouse_id)
    result = await db.execute(
        select(StockItem)
        .join(Ingredient, Ingredient.id == StockItem.ingredient_id)
        .where(StockItem.warehouse_id == warehouse_id)
        .where(StockItem.is_active.is_(True))
        .options(selectinload(StockItem.ingredient))
        .order_by(Ingredient.name),
    )
    rows = [_stock_item_read(item) for item in result.scalars().all()]
    return [item for item in rows if item.is_low_stock] if low_only else rows


@router.post(
    "/stock/warehouses/{warehouse_id}/items",
    response_model=StockItemDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_warehouse_item(
    warehouse_id: int,
    body: StockItemCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StockItemDetailRead:
    await _ensure_warehouse_access(db, current_user, warehouse_id)
    ingredient = await db.get(Ingredient, body.ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono składnika.")
    existing = await crud_stock_item.get_by_warehouse_and_ingredient(
        db,
        warehouse_id=warehouse_id,
        ingredient_id=body.ingredient_id,
    )
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="Ten towar już znajduje się w magazynie.")
        existing.is_active = True
        existing.minimum_quantity = body.minimum_quantity
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        existing.ingredient = ingredient
        return _stock_item_read(existing)
    item = StockItem(
        warehouse_id=warehouse_id,
        ingredient_id=body.ingredient_id,
        quantity=Decimal("0"),
        minimum_quantity=body.minimum_quantity,
        is_active=True,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    item.ingredient = ingredient
    return _stock_item_read(item)


@router.patch(
    "/stock/items/{stock_item_id}/threshold",
    response_model=StockItemDetailRead,
)
async def update_stock_threshold(
    stock_item_id: int,
    body: StockItemThresholdRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StockItemDetailRead:
    item = await db.get(StockItem, stock_item_id, options=[selectinload(StockItem.ingredient)])
    if item is None:
        raise HTTPException(status_code=404, detail="Stock item not found.")
    await _ensure_warehouse_access(db, current_user, item.warehouse_id)
    item.minimum_quantity = body.minimum_quantity
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _stock_item_read(item)


@router.patch(
    "/stock/items/{stock_item_id}",
    response_model=StockItemDetailRead,
)
async def update_warehouse_item(
    stock_item_id: int,
    body: StockItemUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StockItemDetailRead:
    item = await db.get(StockItem, stock_item_id, options=[selectinload(StockItem.ingredient)])
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Nie znaleziono towaru magazynowego.")
    await _ensure_warehouse_access(db, current_user, item.warehouse_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("ingredient_name") is not None:
        item.ingredient.name = data["ingredient_name"].strip()
        db.add(item.ingredient)
    if data.get("unit") is not None:
        item.ingredient.unit = data["unit"].strip()
        db.add(item.ingredient)
    if "minimum_quantity" in data:
        item.minimum_quantity = data["minimum_quantity"]
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _stock_item_read(item)


@router.delete(
    "/stock/items/{stock_item_id}",
    response_model=StockItemDetailRead,
)
async def delete_warehouse_item(
    stock_item_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> StockItemDetailRead:
    item = await db.get(StockItem, stock_item_id, options=[selectinload(StockItem.ingredient)])
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Nie znaleziono towaru magazynowego.")
    await _ensure_warehouse_access(db, current_user, item.warehouse_id)
    if item.quantity != Decimal("0"):
        raise HTTPException(
            status_code=409,
            detail="Nie można usunąć towaru z niezerowym stanem. Najpierw przenieś go lub odpisz.",
        )
    item.is_active = False
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _stock_item_read(item)


@router.post("/stock/documents/receipts", response_model=WarehouseDocumentRead)
async def create_receipt_document(
    body: ReceiptDocumentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> WarehouseDocumentRead:
    await _ensure_warehouse_access(db, current_user, body.warehouse_id)
    try:
        document = await stock_service.receive_stock(
            db,
            warehouse_id=body.warehouse_id,
            lines=_document_lines(body.items),
            issued_by_user_id=current_user.id,
            operation_date=body.operation_date,
            description=body.description,
        )
        return _document_read(document)
    except ValueError as exc:
        await db.rollback()
        raise_bad_request(exc)


@router.post("/stock/documents/transfers", response_model=WarehouseDocumentRead)
async def create_transfer_document(
    body: TransferDocumentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> WarehouseDocumentRead:
    await _ensure_warehouse_access(db, current_user, body.source_warehouse_id)
    await _ensure_warehouse_access(db, current_user, body.destination_warehouse_id)
    try:
        document = await stock_service.transfer_stock(
            db,
            source_warehouse_id=body.source_warehouse_id,
            destination_warehouse_id=body.destination_warehouse_id,
            lines=_document_lines(body.items),
            issued_by_user_id=current_user.id,
            operation_date=body.operation_date,
            description=body.description,
        )
        return _document_read(document)
    except ValueError as exc:
        await db.rollback()
        raise_bad_request(exc)


@router.post("/stock/documents/write-offs", response_model=WarehouseDocumentRead)
async def create_write_off_document(
    body: WriteOffDocumentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> WarehouseDocumentRead:
    await _ensure_warehouse_access(db, current_user, body.warehouse_id)
    try:
        document = await stock_service.write_off_stock(
            db,
            warehouse_id=body.warehouse_id,
            lines=_document_lines(body.items),
            issued_by_user_id=current_user.id,
            operation_date=body.operation_date,
            reason=body.reason,
            description=body.description,
        )
        return _document_read(document)
    except ValueError as exc:
        await db.rollback()
        raise_bad_request(exc)


@router.get("/stock/documents", response_model=list[WarehouseDocumentRead])
async def list_stock_documents(
    db: DbSession,
    current_user: CurrentUser,
    warehouse_id: int | None = Query(default=None),
    document_type: str | None = Query(default=None),
) -> list[WarehouseDocumentRead]:
    accessible = await _accessible_warehouse_ids(db, current_user)
    if warehouse_id is not None and warehouse_id not in accessible:
        raise HTTPException(status_code=403, detail="No access to this warehouse.")
    stmt = (
        select(WarehouseDocument)
        .where(
            or_(
                WarehouseDocument.source_warehouse_id.in_(accessible),
                WarehouseDocument.destination_warehouse_id.in_(accessible),
            ),
        )
        .options(
            selectinload(WarehouseDocument.items).selectinload(WarehouseDocumentItem.ingredient),
            selectinload(WarehouseDocument.source_warehouse),
            selectinload(WarehouseDocument.destination_warehouse),
            selectinload(WarehouseDocument.issued_by_user),
        )
        .order_by(WarehouseDocument.issued_at.desc())
        .limit(200)
    )
    if warehouse_id is not None:
        stmt = stmt.where(
            or_(
                WarehouseDocument.source_warehouse_id == warehouse_id,
                WarehouseDocument.destination_warehouse_id == warehouse_id,
            ),
        )
    if document_type:
        stmt = stmt.where(WarehouseDocument.document_type == document_type.upper())
    result = await db.execute(stmt)
    return [_document_read(document) for document in result.scalars().unique().all()]


@router.get(
    "/stock-items/by-warehouse-and-ingredient",
    response_model=StockItemRead,
)
async def get_stock_item_by_warehouse_and_ingredient(
    warehouse_id: int,
    ingredient_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    _require_legacy_stock_role(current_user)
    stock_item = await crud_stock_item.get_by_warehouse_and_ingredient(
        db,
        warehouse_id=warehouse_id,
        ingredient_id=ingredient_id,
    )
    if stock_item is None:
        raise HTTPException(status_code=404, detail="stock item not found.")
    return stock_item


@router.post(
    "/stock-items/{stock_item_id}/movements/apply",
    response_model=StockMovementRead,
)
async def apply_stock_movement(
    stock_item_id: int,
    body: ApplyStockMovementRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    _require_legacy_stock_role(current_user)
    stock_item = await get_or_404(
        crud_obj=crud_stock_item,
        db=db,
        id=stock_item_id,
        entity_name="stock item",
    )
    try:
        return await stock_service.apply_movement(
            db,
            stock_item=stock_item,
            type=body.type,
            quantity_delta=body.quantity_delta,
            description=body.description,
            prevent_negative=body.prevent_negative,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post(
    "/order-items/{order_item_id}/consume-stock",
    response_model=list[StockMovementRead],
)
async def consume_stock_for_order_item(
    order_item_id: int,
    body: ConsumeOrderItemStockRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    _require_legacy_stock_role(current_user)
    order_item = await get_or_404(
        crud_obj=crud_order_item,
        db=db,
        id=order_item_id,
        entity_name="order item",
    )
    try:
        return await stock_service.consume_ingredients_for_order_item(
            db,
            order_item=order_item,
            warehouse_id=body.warehouse_id,
        )
    except ValueError as exc:
        await db.rollback()
        raise_bad_request(exc)


def _require_admin(user: User) -> None:
    if user.role != ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required.")


def _require_legacy_stock_role(user: User) -> None:
    if user.role not in STOCK_ROLES:
        raise HTTPException(status_code=403, detail="User does not have permission for this action.")


async def _get_warehouse_or_404(db: DbSession, warehouse_id: int) -> Warehouse:
    warehouse = await db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found.")
    return warehouse


async def _accessible_warehouse_ids(db: DbSession, user: User) -> set[int]:
    if user.role == ADMIN:
        return set(
            (
                await db.execute(
                    select(Warehouse.id).where(Warehouse.is_active.is_(True)),
                )
            ).scalars().all(),
        )
    return set(
        (
            await db.execute(
                select(WarehouseUserAccess.warehouse_id)
                .join(Warehouse, Warehouse.id == WarehouseUserAccess.warehouse_id)
                .where(
                    WarehouseUserAccess.user_id == user.id,
                    Warehouse.is_active.is_(True),
                ),
            )
        ).scalars().all(),
    )


async def _ensure_any_warehouse_access(db: DbSession, user: User) -> None:
    if not await _accessible_warehouse_ids(db, user):
        raise HTTPException(status_code=403, detail="No warehouse module access.")


async def _ensure_warehouse_access(db: DbSession, user: User, warehouse_id: int) -> Warehouse:
    warehouse = await _get_warehouse_or_404(db, warehouse_id)
    if not warehouse.is_active:
        raise HTTPException(status_code=404, detail="Magazyn jest nieaktywny.")
    if user.role == ADMIN:
        return warehouse
    access = await db.execute(
        select(WarehouseUserAccess.id).where(
            WarehouseUserAccess.warehouse_id == warehouse_id,
            WarehouseUserAccess.user_id == user.id,
        ),
    )
    if access.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="No access to this warehouse.")
    return warehouse


def _stock_item_read(item: StockItem) -> StockItemDetailRead:
    is_low = (
        item.minimum_quantity is not None
        and item.quantity <= item.minimum_quantity
    )
    return StockItemDetailRead(
        id=item.id,
        warehouse_id=item.warehouse_id,
        ingredient_id=item.ingredient_id,
        ingredient_name=item.ingredient.name,
        unit=item.ingredient.unit,
        quantity=item.quantity,
        minimum_quantity=item.minimum_quantity,
        is_low_stock=is_low,
        is_active=item.is_active,
    )


def _document_lines(items: list[DocumentLineInput]) -> list[tuple[int, Decimal, Decimal | None]]:
    return [(item.ingredient_id, item.quantity, item.unit_price) for item in items]


def _document_read(document: WarehouseDocument) -> WarehouseDocumentRead:
    issued_by = document.issued_by_user
    return WarehouseDocumentRead(
        id=document.id,
        document_number=document.document_number,
        document_type=document.document_type,
        status=document.status,
        source_warehouse_id=document.source_warehouse_id,
        source_warehouse_name=(document.source_warehouse.name if document.source_warehouse else None),
        destination_warehouse_id=document.destination_warehouse_id,
        destination_warehouse_name=(document.destination_warehouse.name if document.destination_warehouse else None),
        order_id=document.order_id,
        issued_by_user_id=document.issued_by_user_id,
        issued_by_name=(
            f"{issued_by.first_name} {issued_by.last_name}" if issued_by is not None else None
        ),
        operation_date=document.operation_date,
        issued_at=document.issued_at,
        reason=document.reason,
        description=document.description,
        items=[
            WarehouseDocumentItemRead(
                id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient.name,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_value=item.total_value,
            )
            for item in document.items
        ],
    )
