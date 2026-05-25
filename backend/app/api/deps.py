from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_or_404(
    *,
    crud_obj: Any,
    db: AsyncSession,
    id: int,
    entity_name: str,
) -> Any:
    db_obj = await crud_obj.get(db, id)
    if db_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} not found.",
        )

    return db_obj


def raise_bad_request(exc: ValueError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    ) from exc


def raise_forbidden(exc: PermissionError) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc),
    ) from exc
