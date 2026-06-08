from app.models.order import Order
from app.models.user import User


class AuthorizationService:
    def require_roles(self, *, user: User, allowed_roles: set[str]) -> None:
        if user.role not in allowed_roles:
            raise PermissionError("User does not have permission for this action.")

    def can_manage_order(self, *, user: User) -> bool:
        return user.role in {"ADMIN", "MANAGER", "WAITER"}

    def require_order_access(self, *, user: User, order: Order) -> None:
        if user.role in {"ADMIN", "MANAGER"}:
            return
        if user.role != "WAITER" or order.waiter_id != user.id:
            raise PermissionError("You cannot modify another employee's order.")

    def can_manage_kitchen(self, *, user: User) -> bool:
        return user.role in {"ADMIN", "MANAGER", "KITCHEN"}

    def can_manage_users(self, *, user: User) -> bool:
        return user.role in {"ADMIN", "MANAGER"}


authorization_service = AuthorizationService()
