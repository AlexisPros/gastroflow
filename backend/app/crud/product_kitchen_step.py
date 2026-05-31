from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.product_kitchen_step import ProductKitchenStep
from app.schemas.product_kitchen_step import (
    ProductKitchenStepCreate,
    ProductKitchenStepUpdate,
)


class CRUDProductKitchenStep(
    CRUDBase[
        ProductKitchenStep,
        ProductKitchenStepCreate,
        ProductKitchenStepUpdate,
    ],
):
    async def get_active_by_product(
        self,
        db: AsyncSession,
        *,
        product_id: int,
    ) -> list[ProductKitchenStep]:
        result = await db.execute(
            select(ProductKitchenStep)
            .where(
                ProductKitchenStep.product_id == product_id,
                ProductKitchenStep.is_active.is_(True),
            )
            .order_by(ProductKitchenStep.sequence),
        )
        return list(result.scalars().all())


product_kitchen_step = CRUDProductKitchenStep(ProductKitchenStep)
