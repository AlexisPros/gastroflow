import asyncio
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from app.db.session import AsyncSessionLocal
from seed_dev_data import (
    DEV_PASSWORD,
    DEV_USERS,
    seed_discounts,
    seed_floor_plan,
    seed_menu,
    seed_restaurant_config,
    seed_stock,
    seed_users,
)

TEST_DATA_TABLES = [
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
    "stock_movements",
]

SERIAL_TABLES = [
    "bill_segment_items",
    "bill_segments",
    "discounts",
    "employee_shift_reports",
    "employee_shifts",
    "floor_plan_decorations",
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
    "product_ingredients",
    "product_kitchen_steps",
    "product_modifiers",
    "products",
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


async def clear_test_data(db: AsyncSession) -> None:
    for table_name in TEST_DATA_TABLES:
        await db.execute(text(f"DELETE FROM {table_name}"))


async def reset_existing_tables(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            UPDATE restaurant_tables
            SET status = 'FREE',
                current_guests = NULL
            """
        )
    )


async def reset_primary_key_sequences(db: AsyncSession) -> None:
    for table_name in SERIAL_TABLES:
        await db.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1,
                    false
                )
                WHERE pg_get_serial_sequence('{table_name}', 'id') IS NOT NULL
                """
            ),
        )


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await clear_test_data(db)
        await reset_existing_tables(db)
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
    print("Clean test seed data created.")
    print("Kept floor plans, floor plan tables, floor plan decorations and restaurant tables.")
    print("Demo password for all users:", DEV_PASSWORD)
    print("Demo users:")
    for _, _, email, role, pin in DEV_USERS:
        print(f"- {email} ({role}), PIN: {pin}")
