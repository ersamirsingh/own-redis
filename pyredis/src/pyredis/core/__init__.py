"""PyRedis core package."""

from pyredis.core.config import settings, Settings
from pyredis.core.types import DataType, Role, FsyncPolicy, EvictionPolicy
from pyredis.core.exceptions import (
    PyRedisException,
    ProtocolError,
    WrongTypeError,
    CommandError,
    AuthError,
    OutOfMemoryError,
)

__all__ = [
    "settings",
    "Settings",
    "DataType",
    "Role",
    "FsyncPolicy",
    "EvictionPolicy",
    "PyRedisException",
    "ProtocolError",
    "WrongTypeError",
    "CommandError",
    "AuthError",
    "OutOfMemoryError",
]
