from datetime import datetime

from pydantic import EmailStr

from app.schemas.base import OrmBaseModel


class UserBase(OrmBaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    is_active: bool = True


class UserCreate(UserBase):
    password: str
    pin: str | None = None


class UserUpdate(OrmBaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    pin: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    id: int
    created_at: datetime
