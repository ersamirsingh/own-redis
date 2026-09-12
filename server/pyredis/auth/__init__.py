"""PyRedis authentication and authorization subsystem."""

from pyredis.auth.audit import AuditLogger, audit_logger
from pyredis.auth.models import (
    ApiKeyCreate,
    ApiKeyResponse,
    AuditLogEntry,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from pyredis.auth.repository import StoredApiKey, StoredUser, UserRepository, user_repo
from pyredis.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)

__all__ = [
    "user_repo",
    "UserRepository",
    "StoredUser",
    "StoredApiKey",
    "audit_logger",
    "AuditLogger",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "RefreshRequest",
    "ApiKeyCreate",
    "ApiKeyResponse",
    "AuditLogEntry",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_api_key",
]
