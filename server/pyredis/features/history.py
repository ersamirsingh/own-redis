"""Time-travel key versioning and revision history."""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pyredis.core.types import DataType


@dataclass
class KeyRevision:
    """Historical snapshot of a key's state."""
    version: int
    timestamp: float
    data_type: DataType
    value_repr: str
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "data_type": self.data_type.value,
            "value_repr": self.value_repr,
            "size_bytes": self.size_bytes,
        }


class HistoryManager:
    """Records and retrieves historical versions for time-travel queries."""

    def __init__(self, max_history_per_key: int = 20) -> None:
        self._history: Dict[str, List[KeyRevision]] = {}
        self._version_counters: Dict[str, int] = {}
        self._max_history = max_history_per_key

    def record_revision(self, key: str, data_type: DataType, value: Any) -> int:
        """Capture a snapshot revision for key before/after mutation."""
        if key not in self._version_counters:
            self._version_counters[key] = 0
            self._history[key] = []

        self._version_counters[key] += 1
        ver = self._version_counters[key]

        # Generate serialized representation
        if data_type in (DataType.STRING, DataType.JSON):
            val_str = str(value)
        elif data_type in (DataType.HASH, DataType.SET, DataType.LIST):
            val_str = str(list(value) if isinstance(value, (set, list)) else dict(value))
        else:
            val_str = repr(value)

        revision = KeyRevision(
            version=ver,
            timestamp=time.time(),
            data_type=data_type,
            value_repr=val_str,
            size_bytes=len(val_str.encode("utf-8")),
        )

        history_list = self._history[key]
        history_list.append(revision)
        if len(history_list) > self._max_history:
            history_list.pop(0)

        return ver

    def get_history(self, key: str) -> List[Dict[str, Any]]:
        """List all available revisions for key in reverse chronological order."""
        revisions = self._history.get(key, [])
        return [r.to_dict() for r in reversed(revisions)]

    def get_revision(self, key: str, version: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific historical version."""
        revisions = self._history.get(key, [])
        for r in revisions:
            if r.version == version:
                return r.to_dict()
        return None

    def clear(self) -> None:
        """Reset version history (for testing)."""
        self._history.clear()
        self._version_counters.clear()


# Global HistoryManager singleton
history_manager = HistoryManager()
