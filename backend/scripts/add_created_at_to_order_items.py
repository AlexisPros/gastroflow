import asyncio
from pathlib import Path
import sys

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.db.session import AsyncSessionLocal


async def run_migration() -> None:
    print("Running migration: adding created_at column to order_items...")
    async with AsyncSessionLocal() as db:
        # 1. Add nullable created_at column
        await db.execute(
            text(
                "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;"
            )
        )
        await db.commit()

        # 2. Update existing rows with their parent order's created_at time
        await db.execute(
            text(
                "UPDATE order_items SET created_at = orders.created_at FROM orders WHERE order_items.order_id = orders.id AND order_items.created_at IS NULL;"
            )
        )
        await db.commit()

        # 3. Set created_at to NOT NULL
        await db.execute(
            text(
                "ALTER TABLE order_items ALTER COLUMN created_at SET NOT NULL;"
            )
        )
        await db.commit()
        print("Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
