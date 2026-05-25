import asyncio
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.core.security import get_password_hash, get_pin_hash
from app.db.session import AsyncSessionLocal
from app.models.discount import Discount
from app.models.floor_plan import FloorPlan
from app.models.floor_plan_table import FloorPlanTable
from app.models.ingredient import Ingredient
from app.models.kitchen_section import KitchenSection
from app.models.modifier import Modifier
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.product_ingredient import ProductIngredient
from app.models.product_modifier import ProductModifier
from app.models.restaurant_config import RestaurantConfig
from app.models.restaurant_table import RestaurantTable
from app.models.stock_item import StockItem
from app.models.system_module import SystemModule
from app.models.user import User
from app.models.warehouse import Warehouse

DEV_PASSWORD = "demo1234"
DEV_PIN = "1234"

TABLES_WITH_SERIAL_ID = [
    "discounts",
    "floor_plans",
    "floor_plan_tables",
    "ingredients",
    "kitchen_sections",
    "modifiers",
    "product_categories",
    "products",
    "product_ingredients",
    "product_modifiers",
    "restaurant_config",
    "restaurant_tables",
    "stock_items",
    "system_modules",
    "users",
    "warehouses",
]


async def reset_primary_key_sequences(db: AsyncSession) -> None:
    for table_name in TABLES_WITH_SERIAL_ID:
        await db.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1,
                    false
                )
                """
            ),
        )


async def get_one(
    db: AsyncSession,
    model: type,
    **filters: Any,
):
    result = await db.execute(
        select(model).filter_by(**filters),
    )
    return result.scalar_one_or_none()


async def get_or_create(
    db: AsyncSession,
    model: type,
    defaults: dict[str, Any] | None = None,
    **filters: Any,
):
    db_obj = await get_one(db, model, **filters)
    if db_obj is not None:
        return db_obj, False

    db_obj = model(**filters, **(defaults or {}))
    db.add(db_obj)
    await db.flush()
    return db_obj, True


async def seed_users(db: AsyncSession) -> None:
    users = [
        ("Admin", "User", "admin@gastroflow.local", "ADMIN"),
        ("Manager", "User", "manager@gastroflow.local", "MANAGER"),
        ("Waiter", "User", "waiter@gastroflow.local", "WAITER"),
        ("Kitchen", "User", "kitchen@gastroflow.local", "KITCHEN"),
        ("Bartender", "User", "bar@gastroflow.local", "BARTENDER"),
    ]

    for first_name, last_name, email, role in users:
        user, created = await get_or_create(
            db,
            User,
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "password_hash": get_password_hash(DEV_PASSWORD),
                "pin_hash": get_pin_hash(DEV_PIN),
                "role": role,
                "is_active": True,
            },
        )
        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.is_active = True


async def seed_restaurant_config(db: AsyncSession) -> RestaurantConfig:
    config, _ = await get_or_create(
        db,
        RestaurantConfig,
        restaurant_name="GastroFlow Demo",
        defaults={
            "currency": "PLN",
        },
    )

    modules = [
        ("QR_ORDERING", True),
        ("KITCHEN_DISPLAY", True),
        ("WAREHOUSE", True),
        ("RESERVATIONS", True),
        ("FISCAL_MOCK", True),
        ("KSEF_MOCK", True),
    ]

    for name, is_enabled in modules:
        module, _ = await get_or_create(
            db,
            SystemModule,
            restaurant_config_id=config.id,
            name=name,
            defaults={
                "is_enabled": is_enabled,
            },
        )
        module.is_enabled = is_enabled

    return config


async def seed_tables(db: AsyncSession) -> list[RestaurantTable]:
    tables: list[RestaurantTable] = []

    for number, seats in [
        ("A1", 2),
        ("A2", 2),
        ("B1", 4),
        ("B2", 4),
        ("C1", 6),
        ("BAR1", 2),
    ]:
        table, _ = await get_or_create(
            db,
            RestaurantTable,
            table_number=number,
            defaults={
                "current_guests": None,
                "status": "FREE",
                "qr_code_url": f"https://gastroflow.local/qr/{number.lower()}",
                "is_active": True,
            },
        )
        table.current_guests = None
        table.status = "FREE"
        table.is_active = True
        if table.qr_code_url is None:
            table.qr_code_url = f"https://gastroflow.local/qr/{number.lower()}"

        tables.append(table)

    return tables


async def seed_menu(db: AsyncSession) -> dict[str, Any]:
    hot, _ = await get_or_create(
        db,
        KitchenSection,
        name="Kuchnia goraca",
        defaults={"is_active": True},
    )
    cold, _ = await get_or_create(
        db,
        KitchenSection,
        name="Kuchnia zimna",
        defaults={"is_active": True},
    )
    bar, _ = await get_or_create(
        db,
        KitchenSection,
        name="Bar",
        defaults={"is_active": True},
    )

    food_category, _ = await get_or_create(
        db,
        ProductCategory,
        name="Dania glowne",
        defaults={"is_active": True},
    )
    drinks_category, _ = await get_or_create(
        db,
        ProductCategory,
        name="Napoje",
        defaults={"is_active": True},
    )

    products_data = [
        (
            "Burger klasyczny",
            food_category,
            hot,
            Decimal("35.00"),
            "Wolowina, ser, salata, sos",
            15,
        ),
        (
            "Salatka cezar",
            food_category,
            cold,
            Decimal("28.00"),
            "Kurczak, salata, grzanki, parmezan",
            10,
        ),
        (
            "Lemoniada",
            drinks_category,
            bar,
            Decimal("12.00"),
            "Domowa lemoniada",
            3,
        ),
    ]

    products: dict[str, Product] = {}
    for name, category, section, price, description, preparation_time in products_data:
        product, _ = await get_or_create(
            db,
            Product,
            name=name,
            defaults={
                "category_id": category.id,
                "kitchen_section_id": section.id,
                "description": description,
                "price": price,
                "preparation_time": preparation_time,
                "is_active": True,
            },
        )
        product.category_id = category.id
        product.kitchen_section_id = section.id
        product.description = description
        product.price = price
        product.preparation_time = preparation_time
        product.is_active = True
        products[name] = product

    modifiers_data = [
        ("Dodatkowy ser", Decimal("4.00")),
        ("Bekon", Decimal("6.00")),
        ("Bez lodu", Decimal("0.00")),
    ]
    modifiers: dict[str, Modifier] = {}
    for name, price in modifiers_data:
        modifier, _ = await get_or_create(
            db,
            Modifier,
            name=name,
            defaults={
                "price": price,
                "is_active": True,
            },
        )
        modifier.price = price
        modifier.is_active = True
        modifiers[name] = modifier

    await link_product_modifier(db, products["Burger klasyczny"], modifiers["Dodatkowy ser"])
    await link_product_modifier(db, products["Burger klasyczny"], modifiers["Bekon"])
    await link_product_modifier(db, products["Lemoniada"], modifiers["Bez lodu"])

    return {
        "products": products,
        "sections": {
            "hot": hot,
            "cold": cold,
            "bar": bar,
        },
    }


async def link_product_modifier(
    db: AsyncSession,
    product: Product,
    modifier: Modifier,
) -> ProductModifier:
    product_modifier, _ = await get_or_create(
        db,
        ProductModifier,
        product_id=product.id,
        modifier_id=modifier.id,
        defaults={
            "price_override": None,
            "is_active": True,
        },
    )
    product_modifier.is_active = True
    return product_modifier


async def seed_stock(
    db: AsyncSession,
    products: dict[str, Product],
) -> None:
    warehouse, _ = await get_or_create(
        db,
        Warehouse,
        name="Magazyn glowny",
        defaults={"type": "MAIN"},
    )
    warehouse.type = "MAIN"

    ingredients_data = [
        ("Bulka burgerowa", "szt", Decimal("100.00"), Decimal("10.00")),
        ("Wolowina", "kg", Decimal("20.00"), Decimal("3.00")),
        ("Ser", "kg", Decimal("8.00"), Decimal("2.00")),
        ("Salata", "kg", Decimal("5.00"), Decimal("1.00")),
        ("Cytryna", "kg", Decimal("6.00"), Decimal("1.00")),
    ]

    ingredients: dict[str, Ingredient] = {}
    for name, unit, quantity, minimum_quantity in ingredients_data:
        ingredient, _ = await get_or_create(
            db,
            Ingredient,
            name=name,
            defaults={
                "unit": unit,
                "is_active": True,
            },
        )
        ingredient.unit = unit
        ingredient.is_active = True
        ingredients[name] = ingredient

        stock_item, _ = await get_or_create(
            db,
            StockItem,
            warehouse_id=warehouse.id,
            ingredient_id=ingredient.id,
            defaults={
                "quantity": quantity,
                "minimum_quantity": minimum_quantity,
            },
        )
        stock_item.quantity = quantity
        stock_item.minimum_quantity = minimum_quantity

    product_ingredients = [
        (products["Burger klasyczny"], ingredients["Bulka burgerowa"], Decimal("1.00")),
        (products["Burger klasyczny"], ingredients["Wolowina"], Decimal("0.20")),
        (products["Burger klasyczny"], ingredients["Ser"], Decimal("0.05")),
        (products["Salatka cezar"], ingredients["Salata"], Decimal("0.15")),
        (products["Lemoniada"], ingredients["Cytryna"], Decimal("0.10")),
    ]

    for product, ingredient, quantity in product_ingredients:
        link, _ = await get_or_create(
            db,
            ProductIngredient,
            product_id=product.id,
            ingredient_id=ingredient.id,
            defaults={
                "quantity": quantity,
            },
        )
        link.quantity = quantity


async def seed_discounts(db: AsyncSession) -> None:
    discounts = [
        ("Rabat 10%", "PERCENT", Decimal("10.00")),
        ("Rabat 20 PLN", "FIXED", Decimal("20.00")),
    ]

    for name, type_, value in discounts:
        discount, _ = await get_or_create(
            db,
            Discount,
            name=name,
            defaults={
                "type": type_,
                "value": value,
                "is_active": True,
            },
        )
        discount.type = type_
        discount.value = value
        discount.is_active = True


async def seed_floor_plan(
    db: AsyncSession,
    tables: list[RestaurantTable],
) -> None:
    floor_plan, _ = await get_or_create(
        db,
        FloorPlan,
        name="Sala glowna",
        defaults={
            "width": 1200,
            "height": 800,
            "is_active": True,
        },
    )
    floor_plan.width = 1200
    floor_plan.height = 800
    floor_plan.is_active = True

    positions = [
        (Decimal("80.00"), Decimal("80.00")),
        (Decimal("260.00"), Decimal("80.00")),
        (Decimal("80.00"), Decimal("240.00")),
        (Decimal("260.00"), Decimal("240.00")),
        (Decimal("480.00"), Decimal("160.00")),
        (Decimal("760.00"), Decimal("80.00")),
    ]

    for table, (x, y) in zip(tables, positions, strict=True):
        floor_plan_table, _ = await get_or_create(
            db,
            FloorPlanTable,
            floor_plan_id=floor_plan.id,
            table_id=table.id,
            defaults={
                "x": x,
                "y": y,
                "width": Decimal("120.00"),
                "height": Decimal("80.00"),
                "rotation": Decimal("0.00"),
                "shape": "RECTANGLE",
            },
        )
        floor_plan_table.x = x
        floor_plan_table.y = y
        floor_plan_table.width = Decimal("120.00")
        floor_plan_table.height = Decimal("80.00")
        floor_plan_table.rotation = Decimal("0.00")
        floor_plan_table.shape = "RECTANGLE"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await reset_primary_key_sequences(db)
        await seed_users(db)
        await seed_restaurant_config(db)
        tables = await seed_tables(db)
        menu = await seed_menu(db)
        await seed_stock(db, menu["products"])
        await seed_discounts(db)
        await seed_floor_plan(db, tables)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
    print("Seed data created.")
    print("Demo password for all users:", DEV_PASSWORD)
    print("Demo PIN for all users:", DEV_PIN)
