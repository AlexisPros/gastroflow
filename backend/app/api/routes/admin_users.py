from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    ADMIN,
    BARTENDER,
    CHEF,
    DbSession,
    KITCHEN,
    MANAGER,
    WAITER,
    WYDAWKA,
    require_roles,
)
from app.core.security import get_pin_lookup
from app.crud import user as crud_user
from app.models.kitchen_section import KitchenSection
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin users"],
    dependencies=[Depends(require_roles({ADMIN}))],
)

USER_ROLES = (ADMIN, MANAGER, WAITER, KITCHEN, CHEF, WYDAWKA, BARTENDER)


class AdminKitchenSectionOption(BaseModel):
    id: int
    name: str
    is_active: bool


class AdminUsersOptionsRead(BaseModel):
    roles: list[str]
    kitchen_sections: list[AdminKitchenSectionOption]


class AdminUserRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    role: str
    kitchen_section_id: int | None
    kitchen_section_name: str | None
    is_active: bool
    has_pin: bool
    created_at: datetime


class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=255)
    pin: str = Field(pattern=r"^\d{4,12}$")
    role: str
    kitchen_section_id: int | None = None
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    pin: str | None = Field(default=None, pattern=r"^\d{4,12}$")
    role: str | None = None
    kitchen_section_id: int | None = None
    is_active: bool | None = None


@router.get("", response_model=list[AdminUserRead])
async def list_admin_users(
    db: DbSession,
    search: str | None = Query(default=None, max_length=120),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> list[AdminUserRead]:
    if role is not None:
        _normalize_role(role)

    stmt = select(User).options(selectinload(User.kitchen_section))

    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.email.ilike(pattern),
            ),
        )

    if role:
        stmt = stmt.where(User.role == role)

    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    stmt = stmt.order_by(User.is_active.desc(), User.role.asc(), User.last_name.asc(), User.first_name.asc())
    result = await db.execute(stmt)
    return [_user_read(item) for item in result.scalars().all()]


@router.get("/options", response_model=AdminUsersOptionsRead)
async def get_admin_users_options(db: DbSession) -> AdminUsersOptionsRead:
    result = await db.execute(
        select(KitchenSection).order_by(KitchenSection.name.asc()),
    )
    return AdminUsersOptionsRead(
        roles=list(USER_ROLES),
        kitchen_sections=[
            AdminKitchenSectionOption(
                id=section.id,
                name=section.name,
                is_active=section.is_active,
            )
            for section in result.scalars().all()
        ],
    )


@router.post("", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def create_admin_user(body: AdminUserCreate, db: DbSession) -> AdminUserRead:
    role = _normalize_role(body.role)
    kitchen_section_id = await _resolve_kitchen_section_id(
        db,
        role=role,
        kitchen_section_id=body.kitchen_section_id,
    )
    await _ensure_email_available(db, email=str(body.email))
    await _ensure_pin_available(db, pin=body.pin)

    created = await crud_user.create(
        db,
        obj_in=UserCreate(
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            email=body.email,
            password=body.password,
            pin=body.pin,
            role=role,
            kitchen_section_id=kitchen_section_id,
            is_active=body.is_active,
        ),
    )
    return _user_read(await _reload_user(db, created.id))


@router.patch("/{user_id}", response_model=AdminUserRead)
async def update_admin_user(
    user_id: int,
    body: AdminUserUpdate,
    db: DbSession,
) -> AdminUserRead:
    db_user = await _get_user_or_404(db, user_id)
    data = body.model_dump(exclude_unset=True)

    if "role" in data and data["role"] is not None:
        data["role"] = _normalize_role(data["role"])

    next_role = data.get("role", db_user.role)
    if "kitchen_section_id" in data or "role" in data:
        data["kitchen_section_id"] = await _resolve_kitchen_section_id(
            db,
            role=next_role,
            kitchen_section_id=data.get("kitchen_section_id", db_user.kitchen_section_id),
        )

    if "email" in data and data["email"] is not None:
        await _ensure_email_available(db, email=str(data["email"]), current_user_id=user_id)

    if "pin" in data and data["pin"] is not None:
        await _ensure_pin_available(db, pin=data["pin"], current_user_id=user_id)

    for field in ("first_name", "last_name"):
        if field in data and isinstance(data[field], str):
            data[field] = data[field].strip()

    updated = await crud_user.update(
        db,
        db_obj=db_user,
        obj_in=UserUpdate(**data),
    )
    return _user_read(await _reload_user(db, updated.id))


@router.patch("/{user_id}/deactivate", response_model=AdminUserRead)
async def deactivate_admin_user(user_id: int, db: DbSession) -> AdminUserRead:
    db_user = await _get_user_or_404(db, user_id)
    db_user.is_active = False
    db.add(db_user)
    await db.commit()
    return _user_read(await _reload_user(db, db_user.id))


@router.patch("/{user_id}/activate", response_model=AdminUserRead)
async def activate_admin_user(user_id: int, db: DbSession) -> AdminUserRead:
    db_user = await _get_user_or_404(db, user_id)
    db_user.is_active = True
    db.add(db_user)
    await db.commit()
    return _user_read(await _reload_user(db, db_user.id))


async def _get_user_or_404(db: DbSession, user_id: int) -> User:
    db_user = await crud_user.get(db, user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return db_user


async def _reload_user(db: DbSession, user_id: int) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.kitchen_section))
        .where(User.id == user_id),
    )
    db_user = result.scalar_one()
    return db_user


async def _ensure_email_available(
    db: DbSession,
    *,
    email: str,
    current_user_id: int | None = None,
) -> None:
    existing = await crud_user.get_by_email(db, email=email)
    if existing is not None and existing.id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
        )


async def _ensure_pin_available(
    db: DbSession,
    *,
    pin: str,
    current_user_id: int | None = None,
) -> None:
    existing = await crud_user.get_by_pin_lookup(db, pin_lookup=get_pin_lookup(pin))
    if existing is not None and existing.id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this PIN already exists.",
        )


async def _resolve_kitchen_section_id(
    db: DbSession,
    *,
    role: str,
    kitchen_section_id: int | None,
) -> int | None:
    if role != KITCHEN:
        return None

    if kitchen_section_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kitchen section is required for kitchen workers.",
        )

    section = await db.get(KitchenSection, kitchen_section_id)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kitchen section not found.",
        )

    if not section.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kitchen section is inactive.",
        )

    return kitchen_section_id


def _normalize_role(role: str) -> str:
    normalized = role.strip().upper()
    if normalized not in USER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported user role.",
        )
    return normalized


def _user_read(user: User) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role,
        kitchen_section_id=user.kitchen_section_id,
        kitchen_section_name=user.kitchen_section.name if user.kitchen_section else None,
        is_active=user.is_active,
        has_pin=user.pin_hash is not None,
        created_at=user.created_at,
    )
