from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DbSession, get_or_404, require_roles
from app.crud import (
    discount,
    floor_plan,
    floor_plan_table,
    ingredient,
    invoice,
    kitchen_section,
    kitchen_task,
    modifier,
    order,
    order_action_log,
    order_item,
    order_item_modifier,
    order_transfer_log,
    payment,
    product,
    product_category,
    product_ingredient,
    product_modifier,
    reservation,
    reservation_table,
    restaurant_config,
    restaurant_table,
    stock_item,
    stock_movement,
    system_module,
    user,
    warehouse,
)
from app.schemas import (
    DiscountCreate,
    DiscountRead,
    DiscountUpdate,
    FloorPlanCreate,
    FloorPlanRead,
    FloorPlanTableCreate,
    FloorPlanTableRead,
    FloorPlanTableUpdate,
    FloorPlanUpdate,
    IngredientCreate,
    IngredientRead,
    IngredientUpdate,
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    KitchenSectionCreate,
    KitchenSectionRead,
    KitchenSectionUpdate,
    KitchenTaskCreate,
    KitchenTaskRead,
    KitchenTaskUpdate,
    ModifierCreate,
    ModifierRead,
    ModifierUpdate,
    OrderActionLogCreate,
    OrderActionLogRead,
    OrderActionLogUpdate,
    OrderCreate,
    OrderItemCreate,
    OrderItemModifierCreate,
    OrderItemModifierRead,
    OrderItemModifierUpdate,
    OrderItemRead,
    OrderItemUpdate,
    OrderRead,
    OrderTransferLogCreate,
    OrderTransferLogRead,
    OrderTransferLogUpdate,
    OrderUpdate,
    PaymentCreate,
    PaymentRead,
    PaymentUpdate,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductIngredientCreate,
    ProductIngredientRead,
    ProductIngredientUpdate,
    ProductModifierCreate,
    ProductModifierRead,
    ProductModifierUpdate,
    ProductRead,
    ProductUpdate,
    ReservationCreate,
    ReservationRead,
    ReservationTableCreate,
    ReservationTableRead,
    ReservationTableUpdate,
    ReservationUpdate,
    RestaurantConfigCreate,
    RestaurantConfigRead,
    RestaurantConfigUpdate,
    RestaurantTableCreate,
    RestaurantTableRead,
    RestaurantTableUpdate,
    StockItemCreate,
    StockItemRead,
    StockItemUpdate,
    StockMovementCreate,
    StockMovementRead,
    StockMovementUpdate,
    SystemModuleCreate,
    SystemModuleRead,
    SystemModuleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
    WarehouseCreate,
    WarehouseRead,
    WarehouseUpdate,
)

router = APIRouter(tags=["CRUD"])

ADMIN_MANAGER = {"ADMIN", "MANAGER"}
STAFF = {"ADMIN", "MANAGER", "WAITER", "KITCHEN", "BARTENDER"}
SERVICE_STAFF = {"ADMIN", "MANAGER", "WAITER"}
KITCHEN_STAFF = {"ADMIN", "MANAGER", "KITCHEN", "BARTENDER"}


def register_crud_routes(
    *,
    path: str,
    crud_obj: Any,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    entity_name: str,
    tag: str,
    read_roles: set[str],
    write_roles: set[str],
) -> None:
    async def list_items(
        db: DbSession,
        skip: int = 0,
        limit: int = 100,
    ):
        return await crud_obj.get_multi(db, skip=skip, limit=limit)

    async def create_item(obj_in, db):
        return await crud_obj.create(db, obj_in=obj_in)

    async def get_item(item_id: int, db: DbSession):
        return await get_or_404(
            crud_obj=crud_obj,
            db=db,
            id=item_id,
            entity_name=entity_name,
        )

    async def update_item(item_id: int, obj_in, db):
        db_obj = await get_or_404(
            crud_obj=crud_obj,
            db=db,
            id=item_id,
            entity_name=entity_name,
        )
        return await crud_obj.update(db, db_obj=db_obj, obj_in=obj_in)

    async def delete_item(item_id: int, db: DbSession):
        db_obj = await crud_obj.delete(db, id=item_id)
        if db_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{entity_name} not found.",
            )

        return db_obj

    create_item.__annotations__ = {
        "obj_in": create_schema,
        "db": DbSession,
    }
    update_item.__annotations__ = {
        "item_id": int,
        "obj_in": update_schema,
        "db": DbSession,
    }

    router.add_api_route(
        path,
        list_items,
        methods=["GET"],
        response_model=list[read_schema],  # pyright: ignore[reportInvalidTypeForm]
        tags=[tag],
        operation_id=f"list_{entity_name}",
        dependencies=[Depends(require_roles(read_roles))],
    )
    router.add_api_route(
        path,
        create_item,
        methods=["POST"],
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
        tags=[tag],
        operation_id=f"create_{entity_name}",
        dependencies=[Depends(require_roles(write_roles))],
    )
    router.add_api_route(
        f"{path}/{{item_id}}",
        get_item,
        methods=["GET"],
        response_model=read_schema,
        tags=[tag],
        operation_id=f"get_{entity_name}",
        dependencies=[Depends(require_roles(read_roles))],
    )
    router.add_api_route(
        f"{path}/{{item_id}}",
        update_item,
        methods=["PATCH"],
        response_model=read_schema,
        tags=[tag],
        operation_id=f"update_{entity_name}",
        dependencies=[Depends(require_roles(write_roles))],
    )
    router.add_api_route(
        f"{path}/{{item_id}}",
        delete_item,
        methods=["DELETE"],
        response_model=read_schema,
        tags=[tag],
        operation_id=f"delete_{entity_name}",
        dependencies=[Depends(require_roles(write_roles))],
    )


register_crud_routes(
    path="/discounts",
    crud_obj=discount,
    create_schema=DiscountCreate,
    update_schema=DiscountUpdate,
    read_schema=DiscountRead,
    entity_name="discount",
    tag="Discounts",
    read_roles=SERVICE_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/floor-plans",
    crud_obj=floor_plan,
    create_schema=FloorPlanCreate,
    update_schema=FloorPlanUpdate,
    read_schema=FloorPlanRead,
    entity_name="floor_plan",
    tag="Floor plans",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/floor-plan-tables",
    crud_obj=floor_plan_table,
    create_schema=FloorPlanTableCreate,
    update_schema=FloorPlanTableUpdate,
    read_schema=FloorPlanTableRead,
    entity_name="floor_plan_table",
    tag="Floor plans",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/ingredients",
    crud_obj=ingredient,
    create_schema=IngredientCreate,
    update_schema=IngredientUpdate,
    read_schema=IngredientRead,
    entity_name="ingredient",
    tag="Ingredients",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/invoices",
    crud_obj=invoice,
    create_schema=InvoiceCreate,
    update_schema=InvoiceUpdate,
    read_schema=InvoiceRead,
    entity_name="invoice",
    tag="Invoices",
    read_roles=SERVICE_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/kitchen-sections",
    crud_obj=kitchen_section,
    create_schema=KitchenSectionCreate,
    update_schema=KitchenSectionUpdate,
    read_schema=KitchenSectionRead,
    entity_name="kitchen_section",
    tag="Kitchen",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/kitchen-tasks",
    crud_obj=kitchen_task,
    create_schema=KitchenTaskCreate,
    update_schema=KitchenTaskUpdate,
    read_schema=KitchenTaskRead,
    entity_name="kitchen_task",
    tag="Kitchen",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/modifiers",
    crud_obj=modifier,
    create_schema=ModifierCreate,
    update_schema=ModifierUpdate,
    read_schema=ModifierRead,
    entity_name="modifier",
    tag="Menu",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/orders",
    crud_obj=order,
    create_schema=OrderCreate,
    update_schema=OrderUpdate,
    read_schema=OrderRead,
    entity_name="order",
    tag="Orders",
    read_roles=SERVICE_STAFF | KITCHEN_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/order-action-logs",
    crud_obj=order_action_log,
    create_schema=OrderActionLogCreate,
    update_schema=OrderActionLogUpdate,
    read_schema=OrderActionLogRead,
    entity_name="order_action_log",
    tag="Orders",
    read_roles=ADMIN_MANAGER,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/order-items",
    crud_obj=order_item,
    create_schema=OrderItemCreate,
    update_schema=OrderItemUpdate,
    read_schema=OrderItemRead,
    entity_name="order_item",
    tag="Orders",
    read_roles=SERVICE_STAFF | KITCHEN_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/order-item-modifiers",
    crud_obj=order_item_modifier,
    create_schema=OrderItemModifierCreate,
    update_schema=OrderItemModifierUpdate,
    read_schema=OrderItemModifierRead,
    entity_name="order_item_modifier",
    tag="Orders",
    read_roles=SERVICE_STAFF | KITCHEN_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/order-transfer-logs",
    crud_obj=order_transfer_log,
    create_schema=OrderTransferLogCreate,
    update_schema=OrderTransferLogUpdate,
    read_schema=OrderTransferLogRead,
    entity_name="order_transfer_log",
    tag="Orders",
    read_roles=ADMIN_MANAGER,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/payments",
    crud_obj=payment,
    create_schema=PaymentCreate,
    update_schema=PaymentUpdate,
    read_schema=PaymentRead,
    entity_name="payment",
    tag="Payments",
    read_roles=SERVICE_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/products",
    crud_obj=product,
    create_schema=ProductCreate,
    update_schema=ProductUpdate,
    read_schema=ProductRead,
    entity_name="product",
    tag="Menu",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/product-categories",
    crud_obj=product_category,
    create_schema=ProductCategoryCreate,
    update_schema=ProductCategoryUpdate,
    read_schema=ProductCategoryRead,
    entity_name="product_category",
    tag="Menu",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/product-ingredients",
    crud_obj=product_ingredient,
    create_schema=ProductIngredientCreate,
    update_schema=ProductIngredientUpdate,
    read_schema=ProductIngredientRead,
    entity_name="product_ingredient",
    tag="Menu",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/product-modifiers",
    crud_obj=product_modifier,
    create_schema=ProductModifierCreate,
    update_schema=ProductModifierUpdate,
    read_schema=ProductModifierRead,
    entity_name="product_modifier",
    tag="Menu",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/reservations",
    crud_obj=reservation,
    create_schema=ReservationCreate,
    update_schema=ReservationUpdate,
    read_schema=ReservationRead,
    entity_name="reservation",
    tag="Reservations",
    read_roles=SERVICE_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/reservation-tables",
    crud_obj=reservation_table,
    create_schema=ReservationTableCreate,
    update_schema=ReservationTableUpdate,
    read_schema=ReservationTableRead,
    entity_name="reservation_table",
    tag="Reservations",
    read_roles=SERVICE_STAFF,
    write_roles=SERVICE_STAFF,
)
register_crud_routes(
    path="/restaurant-config",
    crud_obj=restaurant_config,
    create_schema=RestaurantConfigCreate,
    update_schema=RestaurantConfigUpdate,
    read_schema=RestaurantConfigRead,
    entity_name="restaurant_config",
    tag="Restaurant",
    read_roles=ADMIN_MANAGER,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/restaurant-tables",
    crud_obj=restaurant_table,
    create_schema=RestaurantTableCreate,
    update_schema=RestaurantTableUpdate,
    read_schema=RestaurantTableRead,
    entity_name="restaurant_table",
    tag="Restaurant",
    read_roles=STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/stock-items",
    crud_obj=stock_item,
    create_schema=StockItemCreate,
    update_schema=StockItemUpdate,
    read_schema=StockItemRead,
    entity_name="stock_item",
    tag="Stock",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/stock-movements",
    crud_obj=stock_movement,
    create_schema=StockMovementCreate,
    update_schema=StockMovementUpdate,
    read_schema=StockMovementRead,
    entity_name="stock_movement",
    tag="Stock",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/system-modules",
    crud_obj=system_module,
    create_schema=SystemModuleCreate,
    update_schema=SystemModuleUpdate,
    read_schema=SystemModuleRead,
    entity_name="system_module",
    tag="System",
    read_roles=ADMIN_MANAGER,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/users",
    crud_obj=user,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    read_schema=UserRead,
    entity_name="user",
    tag="Users",
    read_roles=ADMIN_MANAGER,
    write_roles=ADMIN_MANAGER,
)
register_crud_routes(
    path="/warehouses",
    crud_obj=warehouse,
    create_schema=WarehouseCreate,
    update_schema=WarehouseUpdate,
    read_schema=WarehouseRead,
    entity_name="warehouse",
    tag="Stock",
    read_roles=KITCHEN_STAFF,
    write_roles=ADMIN_MANAGER,
)
