import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_roles
from app.core.security import create_access_token, decode_access_token, get_password_hash
from app.crud import user as crud_user
from app.main import app
from app.models.user import User


client = TestClient(app)


def make_user(role: str) -> User:
    return User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash=get_password_hash("secret-password"),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def override_current_user(role: str) -> None:
    async def _get_current_user_override():
        return make_user(role)

    app.dependency_overrides[get_current_user] = _get_current_user_override


def test_create_and_decode_access_token():
    token = create_access_token(
        subject="1",
        extra_claims={"role": "ADMIN"},
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "1"
    assert payload["role"] == "ADMIN"
    assert "exp" in payload


def test_openapi_builds():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/auth/login" in response.json()["paths"]


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


def test_wrong_role_gets_403_on_protected_route():
    override_current_user("WAITER")

    try:
        response = client.get(
            "/api/v1/floor-plans/active",
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
