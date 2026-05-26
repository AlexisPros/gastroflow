from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

import bcrypt
from jose import jwt

from app.core.config import settings


def _sha256_digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        _sha256_digest(password),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            _sha256_digest(plain_password),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def get_pin_hash(pin: str) -> str:
    return bcrypt.hashpw(
        _sha256_digest(pin),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_pin(plain_pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            _sha256_digest(plain_pin),
            pin_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(
    *,
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, str | int | bool] | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, str | int | bool | datetime] = {
        "sub": subject,
        "exp": expire,
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
