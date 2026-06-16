import asyncio
from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.restaurant_table import RestaurantTable
from app.services.qr_code_service import qr_code_service


async def refresh_table_qr_urls() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RestaurantTable).where(RestaurantTable.qr_token.is_not(None)),
        )
        tables = list(result.scalars().all())

        for table in tables:
            table.qr_code_url = qr_code_service.build_table_url(
                qr_token=table.qr_token,
            )
            db.add(table)

        await db.commit()
        print(
            f"Updated {len(tables)} table QR URLs "
            f"using {settings.PUBLIC_MENU_BASE_URL.rstrip('/')}."
        )


if __name__ == "__main__":
    asyncio.run(refresh_table_qr_urls())
