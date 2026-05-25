from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


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


async def get_current_user(
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_error

        user_id = int(subject)
    except (JWTError, ValueError) as exc:
        raise credentials_error from exc

    db_user = await crud_user.get(db, user_id)
    if db_user is None or not db_user.is_active:
        raise credentials_error

    return db_user


CurrentUser = Annotated[User, Depends(get_current_user)]
