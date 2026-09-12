"""Core data types and enumerations for PyRedis."""

from enum import Enum, auto


class DataType(str, Enum):
    """Supported in-memory data types."""
    STRING = "string"
    LIST = "list"
    SET = "set"
    HASH = "hash"
    ZSET = "zset"
    JSON = "json"


class Role(str, Enum):
    """Role hierarchy for Multi-User RBAC."""
    ADMIN = "admin"
    DEVELOPER = "developer"


class FsyncPolicy(str, Enum):
    """Persistence fsync policies."""
    ALWAYS = "always"
    EVERYSEC = "everysec"
    NO = "no"


class EvictionPolicy(str, Enum):
    """Memory eviction policies."""
    NOEVICTION = "noeviction"
    ALLKEYS_LRU = "allkeys-lru"
    VOLATILE_LRU = "volatile-lru"
    ALLKEYS_LFU = "allkeys-lfu"
    ADAPTIVE = "adaptive"
