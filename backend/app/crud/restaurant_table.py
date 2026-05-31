from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.restaurant_table import RestaurantTable
from app.schemas.restaurant_table import RestaurantTableCreate, RestaurantTableUpdate
from app.services.qr_code_service import qr_code_service


class CRUDRestaurantTable(
    CRUDBase[RestaurantTable, RestaurantTableCreate, RestaurantTableUpdate],
):
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: RestaurantTableCreate | dict[str, Any],
    ) -> RestaurantTable:
        obj_data = self._schema_to_dict(obj_in)
        await self._ensure_qr_data(db, obj_data=obj_data)

        db_obj = RestaurantTable(**obj_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def _ensure_qr_data(
        self,
        db: AsyncSession,
        *,
        obj_data: dict[str, Any],
    ) -> None:
        if obj_data.get("qr_token") is None:
            obj_data["qr_token"] = await self._generate_unique_qr_token(
                db,
                table_number=obj_data["table_number"],
            )
        else:
            await self._validate_qr_token_is_unique(
                db,
                qr_token=obj_data["qr_token"],
            )

        if obj_data.get("qr_code_url") is None:
            obj_data["qr_code_url"] = qr_code_service.build_table_url(
                qr_token=obj_data["qr_token"],
            )

    async def _generate_unique_qr_token(
        self,
        db: AsyncSession,
        *,
        table_number: str,
    ) -> str:
        for _ in range(5):
            qr_token = qr_code_service.generate_table_token(
                table_number=table_number,
            )
            result = await db.execute(
                select(RestaurantTable).where(
                    RestaurantTable.qr_token == qr_token,
                ),
            )
            if result.scalar_one_or_none() is None:
                return qr_token

        raise ValueError("Could not generate unique QR token.")

    async def _validate_qr_token_is_unique(
        self,
        db: AsyncSession,
        *,
        qr_token: str,
    ) -> None:
        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.qr_token == qr_token,
            ),
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError("Restaurant table QR token already exists.")


restaurant_table = CRUDRestaurantTable(RestaurantTable)
