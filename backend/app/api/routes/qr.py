from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, ORDER_ROLES, raise_bad_request, require_roles
from app.crud import order as crud_order
from app.crud import restaurant_table as crud_restaurant_table
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.kitchen_task import KitchenTask
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.product_modifier import ProductModifier
from app.schemas import OrderRead
from app.services import order_service, user_service
from app.services.order_service import OrderItemRequest
from app.services.qr_code_service import qr_code_service

router = APIRouter(tags=["QR"])


class PublicQRTableRead(BaseModel):
    id: int
    table_number: str
    status: str
    qr_code_url: str | None = None
    is_active: bool


class PublicQRModifierRead(BaseModel):
    product_modifier_id: int
    name: str
    price: Decimal


class PublicQRProductRead(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None
    image_url: str | None
    ingredients: list[str]
    price: Decimal
    modifiers: list[PublicQRModifierRead]


class PublicQRCategoryRead(BaseModel):
    id: int
    parent_category_id: int | None
    name: str
    department: str
    products: list[PublicQRProductRead]


class PendingQROrderItemModifierRead(BaseModel):
    name: str
    price: Decimal


class PendingQROrderItemRead(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    position: int
    course_number: int
    unit_price: Decimal
    total_price: Decimal
    status: str
    notes: str | None
    modifiers: list[PendingQROrderItemModifierRead]


class QROrderItemInput(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)
    notes: str | None = None
    product_modifier_ids: list[int] = Field(default_factory=list)


class CreateQRPendingOrderRequest(BaseModel):
    guest_count: int = Field(gt=0)
    items: list[QROrderItemInput] = Field(min_length=1)
    order_code: str | None = Field(default=None, max_length=32)


class UnlockPublicQROrderRequest(BaseModel):
    order_code: str = Field(min_length=1, max_length=32)


class ConfirmQRPendingOrderRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class RejectQRPendingOrderRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=12)
    reason: str | None = Field(default=None, max_length=255)


class PublicQROrderDetailModifierRead(BaseModel):
    name: str
    price: Decimal


class PublicQROrderDetailItemRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    course_number: int
    unit_price: Decimal
    total_price: Decimal
    status: str
    notes: str | None
    modifiers: list[PublicQROrderDetailModifierRead]


class PublicQROrderStatusRead(BaseModel):
    order_id: int
    target_order_id: int | None = None
    status: str
    public_status: str
    progress_percent: int
    can_order_more: bool
    items: list[PublicQROrderDetailItemRead] = Field(default_factory=list)


async def build_public_qr_order_status(
    db: DbSession,
    *,
    order_id: int,
) -> PublicQROrderStatusRead:
    order = await crud_order.get(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    status_order = order
    if order.qr_parent_order_id is not None and order.status == "MERGED":
        parent_order = await crud_order.get(db, order.qr_parent_order_id)
        if parent_order is not None:
            status_order = parent_order

    task_result = await db.execute(
        select(KitchenTask.status)
        .join(OrderItem, OrderItem.id == KitchenTask.order_item_id)
        .where(OrderItem.order_id == status_order.id),
    )
    task_statuses = list(task_result.scalars().all())
    completed_tasks = sum(1 for task_status in task_statuses if task_status == "COMPLETED")
    progress_percent = (
        round(completed_tasks / len(task_statuses) * 100)
        if task_statuses
        else 0
    )

    if order.status == "PENDING_CONFIRMATION":
        public_status = "PENDING_CONFIRMATION"
        progress_percent = 0
    elif order.status in {"REJECTED", "CANCELLED"}:
        public_status = "REJECTED"
        progress_percent = 0
    elif task_statuses and completed_tasks == len(task_statuses):
        public_status = "READY"
        progress_percent = 100
    elif status_order.status in {"OPEN", "IN_PROGRESS"} or order.status == "MERGED":
        public_status = "PREPARING"
    elif status_order.status in {"CLOSED", "PAID"}:
        public_status = "CLOSED"
        progress_percent = 100
    else:
        public_status = status_order.status

    item_result = await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id == status_order.id)
        .options(
            selectinload(OrderItem.product),
            selectinload(OrderItem.modifiers)
            .selectinload(OrderItemModifier.product_modifier)
            .selectinload(ProductModifier.modifier),
        )
        .order_by(OrderItem.position, OrderItem.id),
    )
    items = [
        PublicQROrderDetailItemRead(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name,
            quantity=item.quantity,
            course_number=item.course_number,
            unit_price=item.unit_price,
            total_price=item.total_price,
            status=item.status,
            notes=item.notes,
            modifiers=[
                PublicQROrderDetailModifierRead(
                    name=modifier.product_modifier.modifier.name,
                    price=modifier.price,
                )
                for modifier in item.modifiers
            ],
        )
        for item in item_result.scalars().all()
    ]

    return PublicQROrderStatusRead(
        order_id=order.id,
        target_order_id=order.qr_parent_order_id,
        status=order.status,
        public_status=public_status,
        progress_percent=progress_percent,
        can_order_more=(
            public_status in {"PREPARING", "READY"}
            and status_order.status in {"OPEN", "IN_PROGRESS"}
        ),
        items=items,
    )


async def get_table_by_qr_token(qr_token: str, db: DbSession):
    table = await crud_restaurant_table.get_by_qr_token(
        db,
        qr_token=qr_token,
    )
    if table is None or not table.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR table not found.",
        )

    return table


@router.get("/qr/{qr_token}/table", response_model=PublicQRTableRead)
async def get_qr_table(qr_token: str, db: DbSession):
    table = await get_table_by_qr_token(qr_token, db)
    return PublicQRTableRead(
        id=table.id,
        table_number=table.table_number,
        status=table.status,
        qr_code_url=qr_code_service.build_table_url(qr_token=qr_token),
        is_active=table.is_active,
    )


@router.get("/qr/{qr_token}/menu", response_model=list[PublicQRCategoryRead])
async def get_qr_menu(qr_token: str, db: DbSession):
    await get_table_by_qr_token(qr_token, db)
    category_result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.is_active.is_(True))
        .order_by(ProductCategory.name),
    )
    product_result = await db.execute(
        select(Product)
        .where(Product.is_active.is_(True))
        .options(
            selectinload(Product.product_ingredients),
            selectinload(Product.product_modifiers),
        )
        .order_by(Product.name),
    )
    categories = list(category_result.scalars().all())
    products = list(product_result.scalars().all())

    ingredient_ids = {
        product_ingredient.ingredient_id
        for product in products
        for product_ingredient in product.product_ingredients
    }
    modifier_ids = {
        product_modifier.modifier_id
        for product in products
        for product_modifier in product.product_modifiers
        if product_modifier.is_active
    }
    from app.models.ingredient import Ingredient
    from app.models.modifier import Modifier

    ingredients_by_id = {}
    if ingredient_ids:
        ingredient_result = await db.execute(
            select(Ingredient).where(Ingredient.id.in_(ingredient_ids)),
        )
        ingredients_by_id = {
            ingredient.id: ingredient.name
            for ingredient in ingredient_result.scalars().all()
            if ingredient.is_active
        }
    modifiers_by_id = {}
    if modifier_ids:
        modifier_result = await db.execute(
            select(Modifier).where(Modifier.id.in_(modifier_ids)),
        )
        modifiers_by_id = {
            modifier.id: modifier
            for modifier in modifier_result.scalars().all()
            if modifier.is_active
        }

    products_by_category: dict[int, list[PublicQRProductRead]] = {}
    for product in products:
        public_product = PublicQRProductRead(
            id=product.id,
            category_id=product.category_id,
            name=product.name,
            description=product.description,
            image_url=product.image_url,
            ingredients=[
                ingredients_by_id[item.ingredient_id]
                for item in product.product_ingredients
                if item.ingredient_id in ingredients_by_id
            ],
            price=product.price,
            modifiers=[
                PublicQRModifierRead(
                    product_modifier_id=item.id,
                    name=modifiers_by_id[item.modifier_id].name,
                    price=item.price_override
                    if item.price_override is not None
                    else modifiers_by_id[item.modifier_id].price,
                )
                for item in product.product_modifiers
                if item.is_active and item.modifier_id in modifiers_by_id
            ],
        )
        products_by_category.setdefault(product.category_id, []).append(public_product)

    return [
        PublicQRCategoryRead(
            id=category.id,
            parent_category_id=category.parent_category_id,
            name=category.name,
            department=category.department,
            products=products_by_category.get(category.id, []),
        )
        for category in categories
    ]


@router.get(
    "/qr/{qr_token}/image.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_qr_image(
    qr_token: str,
    db: DbSession,
    size: int = Query(default=420, ge=180, le=1200),
    download: bool = False,
):
    table = await get_table_by_qr_token(qr_token, db)
    public_url = qr_code_service.build_table_url(qr_token=qr_token)
    try:
        image = qr_code_service.generate_png(url=public_url, size=size)
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QR image generator is not installed.",
        ) from exc

    disposition = "attachment" if download else "inline"
    return Response(
        content=image,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "Content-Disposition": (
                f'{disposition}; filename="gastroflow-table-{qr_token}.png"'
            ),
        },
    )


@router.post("/qr/{qr_token}/orders", response_model=OrderRead)
async def create_qr_pending_order(
    qr_token: str,
    body: CreateQRPendingOrderRequest,
    db: DbSession,
):
    table = await get_table_by_qr_token(qr_token, db)

    try:
        return await order_service.create_pending_qr_order(
            db,
            table_id=table.id,
            guest_count=body.guest_count,
            order_code=body.order_code,
            items=[
                OrderItemRequest(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    notes=item.notes,
                    product_modifier_ids=item.product_modifier_ids,
                )
                for item in body.items
            ],
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/qr/{qr_token}/orders/unlock", response_model=PublicQROrderStatusRead)
async def unlock_public_qr_order(
    qr_token: str,
    body: UnlockPublicQROrderRequest,
    db: DbSession,
):
    table = await get_table_by_qr_token(qr_token, db)
    try:
        order_id = int(body.order_code.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found for this table.",
        ) from exc

    order = await crud_order.get(db, order_id)
    if (
        order is None
        or order.table_id != table.id
        or order.status not in {"OPEN", "IN_PROGRESS", "PENDING_CONFIRMATION"}
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found for this table.",
        )

    return await build_public_qr_order_status(db, order_id=order.id)


@router.get("/qr/{qr_token}/orders/{order_id}/status", response_model=PublicQROrderStatusRead)
async def get_public_qr_order_status(qr_token: str, order_id: int, db: DbSession):
    table = await get_table_by_qr_token(qr_token, db)
    order = await crud_order.get(db, order_id)
    if order is None or order.table_id != table.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    return await build_public_qr_order_status(db, order_id=order.id)


async def get_service_order_user_by_pin(pin: str, db: DbSession):
    try:
        waiter = await user_service.find_service_order_user_by_pin(
            db,
            pin=pin,
        )
    except ValueError as exc:
        raise_bad_request(exc)

    if waiter is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    return waiter


@router.get(
    "/qr/orders/pending",
    response_model=list[OrderRead],
    dependencies=[Depends(require_roles(ORDER_ROLES))],
)
async def list_pending_qr_orders(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
):
    return await crud_order.get_pending_qr_orders(
        db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/qr/orders/{order_id}/items",
    response_model=list[PendingQROrderItemRead],
    dependencies=[Depends(require_roles(ORDER_ROLES))],
)
async def list_pending_qr_order_items(order_id: int, db: DbSession):
    order = await crud_order.get(db, order_id)
    if order is None or order.source != "QR":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    result = await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id == order_id)
        .options(
            selectinload(OrderItem.modifiers)
            .selectinload(OrderItemModifier.product_modifier)
            .selectinload(ProductModifier.modifier),
        )
        .order_by(OrderItem.position, OrderItem.id),
    )
    return [
        PendingQROrderItemRead(
            id=item.id,
            order_id=item.order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            position=item.position,
            course_number=item.course_number,
            unit_price=item.unit_price,
            total_price=item.total_price,
            status=item.status,
            notes=item.notes,
            modifiers=[
                PendingQROrderItemModifierRead(
                    name=modifier.product_modifier.modifier.name,
                    price=modifier.price,
                )
                for modifier in item.modifiers
            ],
        )
        for item in result.scalars().all()
    ]


@router.post("/qr/orders/{order_id}/confirm", response_model=OrderRead)
async def confirm_qr_pending_order(
    order_id: int,
    body: ConfirmQRPendingOrderRequest,
    db: DbSession,
):
    order = await crud_order.get(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    waiter = await get_service_order_user_by_pin(body.pin, db)

    try:
        return await order_service.confirm_pending_qr_order(
            db,
            order=order,
            waiter_id=waiter.id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/qr/orders/{order_id}/reject", response_model=OrderRead)
async def reject_qr_pending_order(
    order_id: int,
    body: RejectQRPendingOrderRequest,
    db: DbSession,
):
    order = await crud_order.get(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    waiter = await get_service_order_user_by_pin(body.pin, db)
    if waiter.role not in {"ADMIN", "MANAGER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator or manager can reject a QR order.",
        )

    try:
        return await order_service.reject_pending_qr_order(
            db,
            order=order,
            waiter_id=waiter.id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise_bad_request(exc)
