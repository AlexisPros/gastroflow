from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.api.deps import (
    CurrentUser,
    DbSession,
    RequireAdminManager,
    get_or_404,
    raise_forbidden,
)
from app.core.security import create_access_token
from app.crud import user as crud_user
from app.schemas import UserRead
from app.services import authorization_service, user_service

router = APIRouter(tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PinLoginRequest(BaseModel):
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class VerifyPinRequest(BaseModel):
    pin: str


class RoleCheckRequest(BaseModel):
    user_id: int
    allowed_roles: set[str]


class BooleanResponse(BaseModel):
    success: bool


class RoleCheckResponse(BaseModel):
    allowed: bool


class UserCapabilitiesResponse(BaseModel):
    can_manage_order: bool
    can_manage_kitchen: bool
    can_manage_users: bool


def build_token_response(user) -> TokenResponse:
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "role": user.role,
        },
    )

    return TokenResponse(
        access_token=access_token,
        user=UserRead.model_validate(user),
    )


@router.get(
    "/users/by-email",
    response_model=UserRead,
    dependencies=[RequireAdminManager],
)
async def get_user_by_email(email: EmailStr, db: DbSession):
    user = await crud_user.get_by_email(db, email=email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found.",
        )

    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    user = await user_service.authenticate_by_password(
        db,
        email=body.email,
        password=body.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return build_token_response(user)


@router.post("/auth/token", response_model=TokenResponse)
async def token_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    user = await user_service.authenticate_by_password(
        db,
        email=form_data.username,
        password=form_data.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return build_token_response(user)


@router.post("/auth/pin-login", response_model=TokenResponse)
async def pin_login(body: PinLoginRequest, db: DbSession):
    try:
        user = await user_service.find_active_user_by_pin(db, pin=body.pin)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    return build_token_response(user)


@router.get("/auth/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post(
    "/users/{user_id}/verify-pin",
    response_model=BooleanResponse,
    dependencies=[RequireAdminManager],
)
async def verify_user_pin(
    user_id: int,
    body: VerifyPinRequest,
    db: DbSession,
):
    user = await get_or_404(
        crud_obj=crud_user,
        db=db,
        id=user_id,
        entity_name="user",
    )
    return BooleanResponse(
        success=user_service.verify_user_pin(user=user, pin=body.pin),
    )


@router.post(
    "/authorization/check-role",
    response_model=RoleCheckResponse,
    dependencies=[RequireAdminManager],
)
async def check_role(body: RoleCheckRequest, db: DbSession):
    user = await get_or_404(
        crud_obj=crud_user,
        db=db,
        id=body.user_id,
        entity_name="user",
    )
    return RoleCheckResponse(
        allowed=user.role in body.allowed_roles,
    )


@router.post(
    "/authorization/require-role",
    response_model=RoleCheckResponse,
    dependencies=[RequireAdminManager],
)
async def require_role(body: RoleCheckRequest, db: DbSession):
    user = await get_or_404(
        crud_obj=crud_user,
        db=db,
        id=body.user_id,
        entity_name="user",
    )
    try:
        authorization_service.require_roles(
            user=user,
            allowed_roles=body.allowed_roles,
        )
    except PermissionError as exc:
        raise_forbidden(exc)

    return RoleCheckResponse(allowed=True)


@router.get(
    "/authorization/users/{user_id}/capabilities",
    response_model=UserCapabilitiesResponse,
    dependencies=[RequireAdminManager],
)
async def get_user_capabilities(user_id: int, db: DbSession):
    user = await get_or_404(
        crud_obj=crud_user,
        db=db,
        id=user_id,
        entity_name="user",
    )
    return UserCapabilitiesResponse(
        can_manage_order=authorization_service.can_manage_order(user=user),
        can_manage_kitchen=authorization_service.can_manage_kitchen(user=user),
        can_manage_users=authorization_service.can_manage_users(user=user),
    )
