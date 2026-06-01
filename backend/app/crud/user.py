from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, get_pin_hash
from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UserCreate | dict[str, Any],
    ) -> User:
        obj_data = self._schema_to_dict(obj_in)

        password = obj_data.pop("password")
        pin = obj_data.pop("pin", None)

        db_obj = User(
            **obj_data,
            password_hash=get_password_hash(password),
            pin_hash=get_pin_hash(pin) if pin else None,
        )

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: UserUpdate | dict[str, Any],
    ) -> User:
        obj_data = self._schema_to_dict(obj_in, exclude_unset=True)

        password = obj_data.pop("password", None)
        pin = obj_data.pop("pin", None)

        if password is not None:
            obj_data["password_hash"] = get_password_hash(password)

        if pin is not None:
            obj_data["pin_hash"] = get_pin_hash(pin)

        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str,
    ) -> User | None:
        result = await db.execute(
            select(User).where(User.email == email),
        )
        return result.scalar_one_or_none()

    async def get_active_by_roles(
        self,
        db: AsyncSession,
        *,
        roles: set[str],
    ) -> list[User]:
        result = await db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.role.in_(roles),
            ),
        )
        return list(result.scalars().all())


user = CRUDUser(User)
