from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password[:72], password_hash)


def get_pin_hash(pin: str) -> str:
    return pwd_context.hash(pin[:72])


def verify_pin(plain_pin: str, pin_hash: str) -> bool:
    return pwd_context.verify(plain_pin[:72], pin_hash)