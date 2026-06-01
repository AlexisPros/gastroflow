from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.crud import user as crud_user
from app.main import app
from app.models.user import User


client = TestClient(app)


def make_user() -> User:
    return User(
        id=1,
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password_hash="hash",
        role="MANAGER",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_websocket_requires_token():
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/waiters"):
            pass


def test_websocket_connects_with_valid_token(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        return make_user()

    monkeypatch.setattr(crud_user, "get", get)
    token = create_access_token(subject="1")

    with client.websocket_connect(f"/api/v1/ws/waiters?token={token}") as websocket:
        message = websocket.receive_json()

    assert message == {
        "event": "connected",
        "data": {
            "channel": "waiters",
            "user_id": 1,
        },
    }


def test_websocket_rejects_role_without_channel_access(monkeypatch):
    async def get(_db, id: int):
        assert id == 1
        user = make_user()
        user.role = "WAITER"
        return user

    monkeypatch.setattr(crud_user, "get", get)
    token = create_access_token(subject="1")

    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/ws/managers?token={token}"):
            pass
