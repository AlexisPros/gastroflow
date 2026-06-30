import asyncio
from pathlib import Path
import sys

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.db.session import AsyncSessionLocal


async def run_migration() -> None:
    print("Running migration: adding warehouse_id column to products...")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL;"
            )
        )
        await db.commit()
        print("Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
