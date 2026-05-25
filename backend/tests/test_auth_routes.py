from fastapi.testclient import TestClient

from app.core.security import create_access_token, decode_access_token
from app.main import app


client = TestClient(app)


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