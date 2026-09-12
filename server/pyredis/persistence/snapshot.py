"""Point-in-Time Snapshot (RDB) Persistence Engine."""

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pyredis.core.types import DataType
from pyredis.storage import (
    DataStore,
    create_hash,
    create_list,
    create_set,
    create_string,
    create_zset,
)


def _encode_bytes(val: bytes | str) -> str:
    """Encode bytes or string safely into ASCII base64 for portable JSON serialization."""
    if isinstance(val, str):
        return val
    return "b64:" + base64.b64encode(val).decode("ascii")


def _decode_bytes(val: str) -> bytes:
    """Decode string or base64 back into raw bytes."""
    if val.startswith("b64:"):
        return base64.b64decode(val[4:].encode("ascii"))
    return val.encode("utf-8")


class SnapshotEngine:
    """Manages full point-in-time database snapshotting and restoration."""

    MAGIC = "PYREDIS_RDB_V1"

    def __init__(
        self,
        filepath: str = "./data/dump.rdb",
        enabled: bool = True,
    ) -> None:
        self.filepath: Path = Path(filepath)
        self.enabled: bool = enabled
        self._is_saving: bool = False
        self._last_save_time: Optional[float] = None
        self._last_save_duration_ms: float = 0.0
        self._last_save_key_count: int = 0

    def _ensure_dir(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def save(self, store: DataStore, target_path: Optional[str] = None) -> int:
        """Synchronously write point-in-time snapshot to disk. Returns keys saved."""
        dest = Path(target_path) if target_path else self.filepath
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest.with_suffix(".tmp")

        start_time = time.monotonic()
        self._is_saving = True

        data_entries: List[Dict[str, Any]] = []
        now = time.time()

        for key in store.keys("*"):
            obj = store.get(key)
            if obj is None:
                continue

            ttl = store.get_ttl(key)
            expire_at = (now + ttl) if (ttl is not None and ttl > 0) else None

            # Serialize data by type
            serialized_val: Any
            if obj.data_type == DataType.STRING:
                serialized_val = _encode_bytes(obj.value)

            elif obj.data_type == DataType.LIST:
                serialized_val = [_encode_bytes(x) for x in obj.value]

            elif obj.data_type == DataType.SET:
                serialized_val = [_encode_bytes(x) for x in obj.value]

            elif obj.data_type == DataType.HASH:
                serialized_val = {
                    _encode_bytes(k): _encode_bytes(v)
                    for k, v in obj.value.items()
                }

            elif obj.data_type == DataType.ZSET:
                score_map, _ = obj.value
                serialized_val = [
                    {"member": m, "score": score}
                    for m, score in score_map.items()
                ]
            else:
                continue

            data_entries.append({
                "key": key,
                "type": obj.data_type.value,
                "value": serialized_val,
                "expire_at": expire_at,
            })

        snapshot_doc = {
            "magic": self.MAGIC,
            "version": 1,
            "created_at": time.time(),
            "keys_count": len(data_entries),
            "entries": data_entries,
        }

        with open(temp_dest, "w", encoding="utf-8") as f:
            json.dump(snapshot_doc, f, indent=2)

        temp_dest.replace(dest)

        self._is_saving = False
        self._last_save_time = time.time()
        self._last_save_duration_ms = round((time.monotonic() - start_time) * 1000.0, 2)
        self._last_save_key_count = len(data_entries)

        return len(data_entries)

    async def bgsave(self, store: DataStore) -> int:
        """Asynchronously write point-in-time snapshot to disk without blocking event loop."""
        return await asyncio.to_thread(self.save, store)

    def load(self, store: DataStore, target_path: Optional[str] = None) -> int:
        """Load and reconstruct store from snapshot file. Returns keys restored."""
        src = Path(target_path) if target_path else self.filepath
        if not src.exists():
            return 0

        with open(src, "r", encoding="utf-8") as f:
            doc = json.load(f)

        if doc.get("magic") != self.MAGIC:
            raise ValueError(f"Invalid snapshot file format in {src}")

        entries = doc.get("entries", [])
        restored = 0
        now = time.time()

        for item in entries:
            key = item["key"]
            dtype = item["type"]
            val_raw = item["value"]
            expire_at = item.get("expire_at")

            # Skip expired entries
            if expire_at is not None and now >= expire_at:
                continue

            if dtype == DataType.STRING.value:
                obj = create_string(_decode_bytes(val_raw))

            elif dtype == DataType.LIST.value:
                obj = create_list([_decode_bytes(x) for x in val_raw])

            elif dtype == DataType.SET.value:
                obj = create_set({_decode_bytes(x) for x in val_raw})

            elif dtype == DataType.HASH.value:
                hmap = {
                    _decode_bytes(k): _decode_bytes(v)
                    for k, v in val_raw.items()
                }
                obj = create_hash(hmap)

            elif dtype == DataType.ZSET.value:
                obj = create_zset()
                score_map, sl = obj.value
                for elem in val_raw:
                    m = elem["member"]
                    s = float(elem["score"])
                    score_map[m] = s
                    sl.insert(s, m)
                obj.update_size()

            else:
                continue

            store.set(key, obj, expire_at=expire_at)
            restored += 1

        return restored

    def get_status(self) -> Dict[str, Any]:
        """Return operational telemetry for snapshot monitoring."""
        size = self.filepath.stat().st_size if self.filepath.exists() else 0
        return {
            "enabled": self.enabled,
            "filepath": str(self.filepath),
            "is_saving": self._is_saving,
            "last_save_time": self._last_save_time,
            "last_save_duration_ms": self._last_save_duration_ms,
            "last_save_key_count": self._last_save_key_count,
            "file_size_bytes": size,
        }
