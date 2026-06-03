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
from app.models.ingredient import Ingredient
from app.models.kitchen_section import KitchenSection
from app.models.modifier import Modifier
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.product_ingredient import ProductIngredient
from app.models.product_kitchen_step import ProductKitchenStep
from app.models.product_modifier import ProductModifier
from app.models.restaurant_config import RestaurantConfig
from app.models.stock_item import StockItem
from app.models.system_module import SystemModule
from app.models.user import User
from app.models.warehouse import Warehouse

DEV_PASSWORD = "demo1234"
DEV_USERS = [
    ("Admin", "User", "admin@gastroflow.dev", "ADMIN", "1001"),
    ("Manager", "User", "manager@gastroflow.dev", "MANAGER", "1002"),
    ("Waiter", "User", "waiter@gastroflow.dev", "WAITER", "1234"),
    ("Kitchen", "User", "kitchen@gastroflow.dev", "KITCHEN", "2001"),
    ("Bartender", "User", "bar@gastroflow.dev", "BARTENDER", "3001"),
]

OPERATIONAL_TABLES = [
    "bill_segment_items",
    "bill_segments",
    "employee_shift_reports",
    "order_action_logs",
    "order_transfer_logs",
    "invoices",
    "payments",
    "kitchen_tasks",
    "order_item_modifiers",
    "order_items",
    "orders",
    "employee_shifts",
    "reservation_tables",
    "reservations",
    "floor_plan_tables",
    "restaurant_tables",
    "stock_movements",
]

TABLES_WITH_SERIAL_ID = [
    "bill_segment_items",
    "bill_segments",
    "discounts",
    "employee_shift_reports",
    "employee_shifts",
    "floor_plans",
    "floor_plan_tables",
    "ingredients",
    "invoices",
    "kitchen_sections",
    "kitchen_tasks",
    "modifiers",
    "order_action_logs",
    "order_item_modifiers",
    "order_items",
    "order_transfer_logs",
    "orders",
    "payments",
    "product_categories",
    "products",
    "product_ingredients",
    "product_kitchen_steps",
    "product_modifiers",
    "reservations",
    "reservation_tables",
    "restaurant_config",
    "restaurant_tables",
    "stock_items",
    "stock_movements",
    "system_modules",
    "users",
    "warehouses",
]


async def clear_operational_data(db: AsyncSession) -> None:
    for table_name in OPERATIONAL_TABLES:
        await db.execute(text(f"DELETE FROM {table_name}"))


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
    for first_name, last_name, email, role, pin in DEV_USERS:
        legacy_email = email.replace("@gastroflow.dev", "@gastroflow.local")
        user = await get_one(db, User, email=email)
        if user is None:
            user = await get_one(db, User, email=legacy_email)

        if user is None:
            user = User(email=email)
            db.add(user)

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.password_hash = get_password_hash(DEV_PASSWORD)
        user.pin_hash = get_pin_hash(pin)
        user.role = role
        user.is_active = True

    await db.flush()


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
    meat, _ = await get_or_create(
        db,
        KitchenSection,
        name="Stanowisko miesne",
        defaults={"is_active": True},
    )
    pass_section, _ = await get_or_create(
        db,
        KitchenSection,
        name="Wydawka",
        defaults={"is_active": True},
    )
    bar, _ = await get_or_create(
        db,
        KitchenSection,
        name="Bar",
        defaults={"is_active": True},
    )

    hot.is_active = True
    cold.is_active = True
    meat.is_active = True
    pass_section.is_active = True
    bar.is_active = True

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
            meat,
            Decimal("35.00"),
            "Wolowina, ser, salata, sos",
            15,
            Decimal("8.00"),
        ),
        (
            "Salatka cezar",
            food_category,
            cold,
            Decimal("28.00"),
            "Kurczak, salata, grzanki, parmezan",
            10,
            Decimal("8.00"),
        ),
        (
            "Lemoniada",
            drinks_category,
            bar,
            Decimal("12.00"),
            "Domowa lemoniada",
            3,
            Decimal("23.00"),
        ),
    ]

    products: dict[str, Product] = {}
    for name, category, section, price, description, preparation_time, vat_rate in products_data:
        product, _ = await get_or_create(
            db,
            Product,
            name=name,
            defaults={
                "category_id": category.id,
                "kitchen_section_id": None,
                "description": description,
                "price": price,
                "vat_rate": vat_rate,
                "preparation_time": preparation_time,
                "is_active": True,
            },
        )
        product.category_id = category.id
        product.kitchen_section_id = None
        product.description = description
        product.price = price
        product.vat_rate = vat_rate
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

    await link_product_kitchen_step(
        db,
        product=products["Burger klasyczny"],
        section=meat,
        name="Przygotowanie miesa",
        description="Przygotowanie i obrobka miesa do burgera.",
        sequence=1,
        estimated_time=12,
    )
    await link_product_kitchen_step(
        db,
        product=products["Burger klasyczny"],
        section=hot,
        name="Zlozenie burgera",
        description="Zlozenie burgera i przygotowanie cieplych dodatkow.",
        sequence=2,
        estimated_time=5,
    )
    await link_product_kitchen_step(
        db,
        product=products["Salatka cezar"],
        section=cold,
        name="Przygotowanie salatki",
        description="Przygotowanie warzyw, sosu i skladanie salatki.",
        sequence=1,
        estimated_time=7,
    )
    await link_product_kitchen_step(
        db,
        product=products["Salatka cezar"],
        section=meat,
        name="Przygotowanie dodatku miesnego",
        description="Przygotowanie kurczaka lub krewetek do salatki.",
        sequence=2,
        estimated_time=8,
    )
    await link_product_kitchen_step(
        db,
        product=products["Lemoniada"],
        section=bar,
        name="Przygotowanie napoju",
        description="Przygotowanie napoju na barze.",
        sequence=1,
        estimated_time=3,
    )

    return {
        "products": products,
        "sections": {
            "hot": hot,
            "cold": cold,
            "meat": meat,
            "pass": pass_section,
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


async def link_product_kitchen_step(
    db: AsyncSession,
    *,
    product: Product,
    section: KitchenSection,
    name: str,
    description: str,
    sequence: int,
    estimated_time: int,
) -> ProductKitchenStep:
    step, _ = await get_or_create(
        db,
        ProductKitchenStep,
        product_id=product.id,
        sequence=sequence,
        defaults={
            "kitchen_section_id": section.id,
            "name": name,
            "description": description,
            "estimated_time": estimated_time,
            "is_active": True,
        },
    )
    step.kitchen_section_id = section.id
    step.name = name
    step.description = description
    step.estimated_time = estimated_time
    step.is_active = True
    return step


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


async def seed_floor_plan(db: AsyncSession) -> None:
    floor_plan, _ = await get_or_create(
        db,
        FloorPlan,
        name="Sala glowna",
        defaults={
            "width": 1200,
            "height": 800,
            "background_image_url": None,
            "is_active": True,
        },
    )
    floor_plan.width = 1200
    floor_plan.height = 800
    floor_plan.background_image_url = None
    floor_plan.is_active = True


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await clear_operational_data(db)
        await seed_users(db)
        await seed_restaurant_config(db)
        menu = await seed_menu(db)
        await seed_stock(db, menu["products"])
        await seed_discounts(db)
        await seed_floor_plan(db)
        await reset_primary_key_sequences(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
    print("Seed data created.")
    print("Demo password for all users:", DEV_PASSWORD)
    print("Demo users:")
    for _, _, email, role, pin in DEV_USERS:
        print(f"- {email} ({role}), PIN: {pin}")
