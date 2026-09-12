"""Cryptographic utilities: Argon2id password hashing and JWT token management."""

import secrets
import time
from typing import Any, Dict, Optional, Tuple
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pyredis.core.config import settings
from pyredis.core.exceptions import AuthError
from pyredis.core.types import Role

# Initialize Argon2id password hasher
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB memory-hard
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: Role) -> str:
    """Create a short-lived JWT access token."""
    now = time.time()
    expire = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "type": "access",
        "iat": int(now),
        "exp": int(expire),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, email: str, role: Role) -> str:
    """Create a long-lived rotated JWT refresh token."""
    now = time.time()
    expire = now + (settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "iat": int(now),
        "exp": int(expire),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Decode and cryptographically verify a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != expected_type:
            raise AuthError(f"Invalid token type: expected {expected_type}")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}")


def generate_api_key() -> Tuple[str, str]:
    """Generate a raw API key and its safe preview string."""
    raw = f"sk-pyredis-{secrets.token_urlsafe(32)}"
    preview = f"sk-pyredis-...{raw[-4:]}"
    return raw, preview
