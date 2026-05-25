from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, verify_pin
from app.crud import user
from app.models.user import User


class UserService:
    async def authenticate_by_password(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> User | None:
        db_user = await user.get_by_email(db, email=email)
        if db_user is None or not db_user.is_active:
            return None

        if not verify_password(password, db_user.password_hash):
            return None

        return db_user

    async def authenticate_by_pin(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        pin: str,
    ) -> User | None:
        db_user = await user.get(db, id=user_id)
        if db_user is None or not db_user.is_active:
            return None

        if not self.verify_user_pin(user=db_user, pin=pin):
            return None

        return db_user

    def verify_user_pin(self, *, user: User, pin: str) -> bool:
        if user.pin_hash is None:
            return False

        return verify_pin(pin, user.pin_hash)


user_service = UserService()
