import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_roles
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    get_pin_hash,
    verify_password,
    verify_pin,
)
from app.crud import restaurant_table as crud_restaurant_table
from app.crud import user as crud_user
from app.main import app
from app.models.restaurant_table import RestaurantTable
from app.models.user import User


client = TestClient(app)


def make_user(role: str) -> User:
    return User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash=get_password_hash("secret-password"),
        pin_hash=get_pin_hash("1234"),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def make_restaurant_table() -> RestaurantTable:
    return RestaurantTable(
        id=1,
        table_number="A1",
        current_guests=None,
        status="FREE",
        qr_code_url=None,
        is_active=True,
    )


def test_create_and_decode_access_token():
    token = create_access_token(
        subject="1",
        extra_claims={"role": "ADMIN"},
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert payload["role"] == "ADMIN"
    assert "exp" in payload


def test_invalid_hashes_do_not_raise():
    assert verify_password("secret-password", "not-a-valid-bcrypt-hash") is False
    assert verify_pin("1234", "not-a-valid-bcrypt-hash") is False


def test_openapi_builds():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    assert "/api/v1/auth/login" in openapi["paths"]
    assert "/api/v1/auth/token" in openapi["paths"]
    assert (
        openapi["components"]["securitySchemes"]["OAuth2PasswordBearer"][
            "flows"
        ]["password"]["tokenUrl"]
        == "/api/v1/auth/token"
    )


def test_auth_me_requires_token():
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_protected_order_route_requires_token():
    response = client.post(
        "/api/v1/orders/with-items",
        json={
            "source": "WAITER",
            "items": [
                {
                    "product_id": 1,
                    "quantity": 1,
                    "product_modifier_ids": [],
                }
            ],
        },
    )

    assert response.status_code == 401


def test_auth_me_returns_current_user_with_token_override():
    override_current_user("ADMIN")

    try:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
    assert response.json()["role"] == "ADMIN"


def test_admin_role_passes_role_guard():
    checker = require_roles({"ADMIN", "MANAGER"})
    user = make_user("ADMIN")

    result = asyncio.run(checker(user))

    assert result is user


def test_wrong_role_fails_role_guard():
    checker = require_roles({"ADMIN", "MANAGER"})
    user = make_user("WAITER")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(checker(user))

    assert exc_info.value.status_code == 403


def test_wrong_role_gets_403_on_protected_write_route():
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/floor-plans/1/activate",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_login_returns_access_token(monkeypatch):
    test_user = make_user("ADMIN")

    async def get_by_email(_db, *, email: str):
        if email == test_user.email:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get_by_email", get_by_email)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "secret-password",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == test_user.email

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_user.id)
    assert payload["role"] == "ADMIN"


def test_login_rejects_wrong_password(monkeypatch):
    test_user = make_user("ADMIN")

    async def get_by_email(_db, *, email: str):
        if email == test_user.email:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get_by_email", get_by_email)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


def test_token_login_returns_access_token_for_swagger(monkeypatch):
    test_user = make_user("ADMIN")

    async def get_by_email(_db, *, email: str):
        if email == test_user.email:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get_by_email", get_by_email)

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user.email,
            "password": "secret-password",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == test_user.email

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_user.id)
    assert payload["role"] == "ADMIN"


def test_pin_login_returns_access_token(monkeypatch):
    test_user = make_user("WAITER")

    async def get(_db, id: int):
        if id == test_user.id:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get", get)

    response = client.post(
        "/api/v1/auth/pin-login",
        json={
            "user_id": test_user.id,
            "pin": "1234",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == test_user.email

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_user.id)
    assert payload["role"] == "WAITER"


def test_pin_login_rejects_wrong_pin(monkeypatch):
    test_user = make_user("WAITER")

    async def get(_db, id: int):
        if id == test_user.id:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get", get)

    response = client.post(
        "/api/v1/auth/pin-login",
        json={
            "user_id": test_user.id,
            "pin": "9999",
        },
    )

    assert response.status_code == 401


def test_login_token_can_access_auth_me(monkeypatch):
    test_user = make_user("MANAGER")

    async def get_by_email(_db, *, email: str):
        if email == test_user.email:
            return test_user
        return None

    async def get(_db, id: int):
        if id == test_user.id:
            return test_user
        return None

    monkeypatch.setattr(crud_user, "get_by_email", get_by_email)
    monkeypatch.setattr(crud_user, "get", get)

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "secret-password",
        },
    )
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_user.email
    assert me_response.json()["role"] == "MANAGER"


def test_resource_route_requires_token():
    response = client.get("/api/v1/restaurant-tables")

    assert response.status_code == 401


def test_resource_create_forbidden_for_wrong_role():
    override_current_user("WAITER")

    try:
        response = client.post(
            "/api/v1/restaurant-tables",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "table_number": "A1",
                "current_guests": None,
                "qr_code_url": None,
                "is_active": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_resource_list_with_allowed_role_reaches_crud(monkeypatch):
    async def get_multi(_db, *, skip: int = 0, limit: int = 100):
        assert skip == 0
        assert limit == 100
        return [make_restaurant_table()]

    monkeypatch.setattr(crud_restaurant_table, "get_multi", get_multi)
    override_current_user("MANAGER")

    try:
        response = client.get(
            "/api/v1/restaurant-tables",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["table_number"] == "A1"


def test_resource_create_with_allowed_role_reaches_crud(monkeypatch):
    async def create(_db, *, obj_in):
        assert obj_in.table_number == "A2"
        table = make_restaurant_table()
        table.table_number = obj_in.table_number
        return table

    monkeypatch.setattr(crud_restaurant_table, "create", create)
    override_current_user("MANAGER")

    try:
        response = client.post(
            "/api/v1/restaurant-tables",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "table_number": "A2",
                "current_guests": None,
                "qr_code_url": None,
                "is_active": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["table_number"] == "A2"


def test_resource_update_with_allowed_role_reaches_crud(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_restaurant_table()

    async def update(_db, *, db_obj, obj_in):
        assert db_obj.id == 1
        assert obj_in.status == "OCCUPIED"
        db_obj.status = obj_in.status
        return db_obj

    monkeypatch.setattr(crud_restaurant_table, "get", get)
    monkeypatch.setattr(crud_restaurant_table, "update", update)
    override_current_user("MANAGER")

    try:
        response = client.patch(
            "/api/v1/restaurant-tables/1",
            headers={"Authorization": "Bearer fake-token"},
            json={"status": "OCCUPIED"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "OCCUPIED"


def test_resource_delete_with_allowed_role_reaches_crud(monkeypatch):
    async def delete(_db, *, id: int):
        assert id == 1
        return make_restaurant_table()

    monkeypatch.setattr(crud_restaurant_table, "delete", delete)
    override_current_user("MANAGER")

    try:
        response = client.delete(
            "/api/v1/restaurant-tables/1",
            headers={"Authorization": "Bearer fake-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["table_number"] == "A1"
