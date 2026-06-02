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
    async def get_by_table_number(
        self,
        db: AsyncSession,
        *,
        table_number: str,
    ) -> RestaurantTable | None:
        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.table_number == table_number,
            ),
        )
        return result.scalar_one_or_none()

    async def get_by_qr_token(
        self,
        db: AsyncSession,
        *,
        qr_token: str,
    ) -> RestaurantTable | None:
        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.qr_token == qr_token,
            ),
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: RestaurantTableCreate | dict[str, Any],
    ) -> RestaurantTable:
        obj_data = self._schema_to_dict(obj_in)
        await self._validate_table_number_is_unique(
            db,
            table_number=obj_data["table_number"],
        )
        await self._ensure_qr_data(db, obj_data=obj_data)

        db_obj = RestaurantTable(**obj_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: RestaurantTable,
        obj_in: RestaurantTableUpdate | dict[str, Any],
    ) -> RestaurantTable:
        obj_data = self._schema_to_dict(obj_in, exclude_unset=True)
        table_number = obj_data.get("table_number")
        if table_number is not None and table_number != db_obj.table_number:
            await self._validate_table_number_is_unique(
                db,
                table_number=table_number,
                current_table_id=db_obj.id,
            )

        return await super().update(db, db_obj=db_obj, obj_in=obj_data)

    async def _validate_table_number_is_unique(
        self,
        db: AsyncSession,
        *,
        table_number: str,
        current_table_id: int | None = None,
    ) -> None:
        existing_table = await self.get_by_table_number(
            db,
            table_number=table_number,
        )
        if existing_table is not None and existing_table.id != current_table_id:
            raise ValueError("Table number already exists.")

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
