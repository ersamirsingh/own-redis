"""Primary In-Memory Data Store."""

import fnmatch
import time
from typing import Dict, List, Optional, Tuple
from pyredis.core.exceptions import WrongTypeError
from pyredis.core.types import DataType
from pyredis.storage.object import PyRedisObject


class DataStore:
    """Core key-value dictionary and memory management engine."""

    def __init__(self) -> None:
        self._data: Dict[str, PyRedisObject] = {}
        self._ttl: Dict[str, float] = {}  # key -> expiry unix timestamp in seconds
        self._total_bytes: int = 0

    def get(self, key: str) -> Optional[PyRedisObject]:
        """Lookup key, automatically checking lazy expiration."""
        if self.is_expired(key):
            self.delete(key)
            return None

        obj = self._data.get(key)
        if obj is not None:
            obj.touch()
        return obj

    def set(self, key: str, obj: PyRedisObject, expire_at: Optional[float] = None) -> None:
        """Store key-object mapping and optionally set TTL timestamp."""
        old = self._data.get(key)
        if old:
            self._total_bytes -= old.estimated_bytes

        self._data[key] = obj
        self._total_bytes += obj.estimated_bytes

        try:
            from pyredis.features.history import history_manager
            history_manager.record_revision(key, obj.data_type, obj.value)
        except Exception:
            pass

        if expire_at is not None:
            self._ttl[key] = expire_at
        elif key in self._ttl:
            # Overwriting a key clears existing TTL unless explicitly preserved
            del self._ttl[key]

    def delete(self, key: str) -> bool:
        """Remove key from store and TTL tracking. Returns True if deleted."""
        obj = self._data.pop(key, None)
        self._ttl.pop(key, None)
        if obj is not None:
            self._total_bytes = max(0, self._total_bytes - obj.estimated_bytes)
            return True
        return False

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def get_type(self, key: str) -> Optional[DataType]:
        """Return DataType of key, or None if key does not exist."""
        obj = self.get(key)
        return obj.data_type if obj else None

    def ensure_type(self, key: str, expected: DataType) -> Optional[PyRedisObject]:
        """Get object ensuring data type matches expected, raising WrongTypeError on mismatch."""
        obj = self.get(key)
        if obj is None:
            return None
        if obj.data_type != expected:
            raise WrongTypeError()
        return obj

    # Expiration Management
    def is_expired(self, key: str) -> bool:
        """Check if key has passed its expiration timestamp."""
        exp = self._ttl.get(key)
        if exp is None:
            return False
        return time.time() >= exp

    def set_ttl(self, key: str, expire_at: float) -> bool:
        """Set absolute expiration epoch timestamp in seconds. Returns False if key doesn't exist."""
        if key not in self._data:
            return False
        self._ttl[key] = expire_at
        return True

    def get_ttl(self, key: str) -> Optional[float]:
        """Get remaining TTL in seconds. Returns -2 if missing/expired, -1 if no TTL, or seconds."""
        if not self.exists(key):
            return -2.0
        exp = self._ttl.get(key)
        if exp is None:
            return -1.0
        remaining = exp - time.time()
        return max(0.0, remaining)

    def persist(self, key: str) -> bool:
        """Remove TTL from key. Returns True if TTL was removed."""
        if not self.exists(key):
            return False
        if key in self._ttl:
            del self._ttl[key]
            return True
        return False

    # Server Operations
    def keys(self, pattern: str = "*") -> List[str]:
        """Find keys matching glob pattern, ignoring expired keys."""
        # Evict any expired keys encountered
        now = time.time()
        expired = [k for k, exp in self._ttl.items() if now >= exp]
        for k in expired:
            self.delete(k)

        if pattern == "*":
            return list(self._data.keys())
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    def dbsize(self) -> int:
        """Return number of valid keys in the database."""
        # Run lazy check on ttl keys
        now = time.time()
        expired = [k for k, exp in self._ttl.items() if now >= exp]
        for k in expired:
            self.delete(k)
        return len(self._data)

    def flushdb(self) -> None:
        """Clear all keys, TTLs, and memory counters."""
        self._data.clear()
        self._ttl.clear()
        self._total_bytes = 0

    # Telemetry & Diagnostics
    def memory_usage(self) -> int:
        """Return estimated total memory used by data store in bytes."""
        return self._total_bytes

    def get_largest_keys(self, limit: int = 10) -> List[Tuple[str, DataType, int]]:
        """Return top largest keys sorted by memory size descending."""
        items = [
            (k, obj.data_type, obj.estimated_bytes)
            for k, obj in self._data.items()
            if not self.is_expired(k)
        ]
        items.sort(key=lambda x: x[2], reverse=True)
        return items[:limit]
