"""PyRedis object wrapper with metadata tracking for memory, recency, and frequency."""

import sys
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple
from pyredis.core.types import DataType
from pyredis.storage.skiplist import SkipList


class PyRedisObject:
    """Encapsulates in-memory value with operational telemetry and metadata."""

    __slots__ = (
        "data_type",
        "value",
        "created_at",
        "last_accessed_at",
        "access_count",
        "estimated_bytes",
    )

    def __init__(self, data_type: DataType, value: Any) -> None:
        now = time.monotonic()
        self.data_type: DataType = data_type
        self.value: Any = value
        self.created_at: float = now
        self.last_accessed_at: float = now
        self.access_count: int = 1
        self.estimated_bytes: int = self._estimate_size()

    def touch(self) -> None:
        """Update recency and frequency metrics on read/write access."""
        self.last_accessed_at = time.monotonic()
        self.access_count += 1

    def update_size(self) -> None:
        """Recalculate cached memory size."""
        self.estimated_bytes = self._estimate_size()

    def _estimate_size(self) -> int:
        """Estimate in-memory byte footprint."""
        base = sys.getsizeof(self)
        val = self.value

        if self.data_type == DataType.STRING:
            return base + sys.getsizeof(val)

        elif self.data_type == DataType.LIST:
            # val is deque
            size = base + sys.getsizeof(val)
            for item in val:
                size += sys.getsizeof(item)
            return size

        elif self.data_type == DataType.SET:
            # val is set
            size = base + sys.getsizeof(val)
            for item in val:
                size += sys.getsizeof(item)
            return size

        elif self.data_type == DataType.HASH:
            # val is dict
            size = base + sys.getsizeof(val)
            for k, v in val.items():
                size += sys.getsizeof(k) + sys.getsizeof(v)
            return size

        elif self.data_type == DataType.ZSET:
            # val is (dict, SkipList)
            dict_map, sl = val
            size = base + sys.getsizeof(dict_map)
            for k, v in dict_map.items():
                size += sys.getsizeof(k) + sys.getsizeof(v)
            # Estimate skiplist node size (approx 64 bytes per node)
            size += sl.length * 64
            return size

        elif self.data_type == DataType.JSON:
            return base + len(str(val).encode("utf-8"))

        return base + sys.getsizeof(val)


# Factory constructors for typed objects
def create_string(val: str | bytes) -> PyRedisObject:
    return PyRedisObject(DataType.STRING, val)


def create_list(items: Optional[List[str | bytes]] = None) -> PyRedisObject:
    return PyRedisObject(DataType.LIST, deque(items or []))


def create_set(members: Optional[Set[str | bytes]] = None) -> PyRedisObject:
    return PyRedisObject(DataType.SET, set(members or []))


def create_hash(mapping: Optional[Dict[str, str | bytes]] = None) -> PyRedisObject:
    return PyRedisObject(DataType.HASH, dict(mapping or {}))


def create_zset() -> PyRedisObject:
    # (member -> score dict, SkipList)
    return PyRedisObject(DataType.ZSET, ({}, SkipList()))


def create_json(val: Any) -> PyRedisObject:
    return PyRedisObject(DataType.JSON, val)
