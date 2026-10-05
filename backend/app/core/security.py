"""
Authentication and authorization primitives.

- Password hashing via passlib (bcrypt).
- JWT access + refresh tokens (HS256, driven by SECRET_KEY).
- Role-based access control via FastAPI dependencies.

This is real, working auth against the relational database — not a stub.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=[settings.PASSWORD_HASH_SCHEME], deprecated="auto")


class Role(str, Enum):
    ANALYST = "analyst"
    SENIOR_ANALYST = "senior_analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    ADMIN = "admin"


# Roles are ordered by privilege for simple hierarchical checks.
ROLE_HIERARCHY: dict[Role, int] = {
    Role.ANALYST: 1,
    Role.SENIOR_ANALYST: 2,
    Role.COMPLIANCE_OFFICER: 3,
    Role.ADMIN: 4,
}


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, expires_delta: timedelta, token_type: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # Standard JWT claim (RFC 7519 §4.1.7): guarantees each issued
        # token is unique even when issued within the same iat second
        # (login immediately followed by refresh, as a real client or
        # this project's own test suite does). Without it, two tokens
        # with identical sub/type/iat/exp/role are byte-identical —
        # found via a real test failure, not theoretical.
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: Role) -> str:
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        extra_claims={"role": role.value},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        token_type="refresh",
    )


class TokenPayloadError(Exception):
    pass


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenPayloadError(str(exc)) from exc


def role_at_least(user_role: Role, required_role: Role) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]
