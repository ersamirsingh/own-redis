"""Append-Only File (AOF) Persistence Engine."""

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pyredis.commands.registry import CommandContext, CommandRegistry
from pyredis.core.types import DataType, FsyncPolicy, Role
from pyredis.protocol.encoder import RespEncoder
from pyredis.protocol.parser import RespParser
from pyredis.storage.store import DataStore


class AofEngine:
    """Manages Append-Only File logging, fsync strategies, replay, and compaction."""

    def __init__(
        self,
        filepath: str = "./data/appendonly.aof",
        fsync_policy: FsyncPolicy = FsyncPolicy.EVERYSEC,
        enabled: bool = True,
    ) -> None:
        self.filepath: Path = Path(filepath)
        self.fsync_policy: FsyncPolicy = fsync_policy
        self.enabled: bool = enabled

        self._file = None
        self._fd: Optional[int] = None
        self._fsync_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._writes_total: int = 0
        self._last_fsync_time: float = time.time()

        if self.enabled:
            self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def open(self) -> None:
        """Open AOF file descriptor for appending."""
        if not self.enabled:
            return
        self._ensure_dir()
        self._file = open(self.filepath, "a+b", buffering=0)
        self._fd = self._file.fileno()

    def close(self) -> None:
        """Flush and close AOF file."""
        if self._file:
            try:
                if self._fd is not None:
                    os.fsync(self._fd)
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._fd = None

    def start_background_fsync(self) -> None:
        """Start periodic fsync worker for EVERYSEC policy."""
        if self.enabled and self.fsync_policy == FsyncPolicy.EVERYSEC:
            if self._fsync_task is None or self._fsync_task.done():
                self._running = True
                self._fsync_task = asyncio.create_task(self._fsync_loop())

    async def stop_background_fsync(self) -> None:
        """Stop periodic fsync worker."""
        self._running = False
        if self._fsync_task:
            self._fsync_task.cancel()
            try:
                await self._fsync_task
            except asyncio.CancelledError:
                pass
            self._fsync_task = None
        if self._fd is not None:
            try:
                os.fsync(self._fd)
            except Exception:
                pass

    async def _fsync_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(1.0)
                if self._fd is not None:
                    os.fsync(self._fd)
                    self._last_fsync_time = time.time()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def append(self, cmd_name: str, args: List[Union[bytes, str]]) -> None:
        """Append mutating command to AOF in standard RESP array format."""
        if not self.enabled:
            return

        if self._file is None:
            self.open()

        # Format as RESP Array: *N \r\n $len \r\n CMD \r\n ...
        cmd_tokens: List[Union[bytes, str]] = [cmd_name] + args
        encoded = RespEncoder.encode_array(cmd_tokens)

        if self._file:
            self._file.write(encoded)
            self._writes_total += 1

            if self.fsync_policy == FsyncPolicy.ALWAYS and self._fd is not None:
                os.fsync(self._fd)
                self._last_fsync_time = time.time()

    def replay(self, store: DataStore, registry: CommandRegistry) -> int:
        """Replay commands from AOF into store upon startup. Returns replayed count."""
        if not self.filepath.exists():
            return 0

        replayed_count = 0
        parser = RespParser()
        context = CommandContext(store=store, role=Role.ADMIN)

        with open(self.filepath, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                parser.feed(chunk)

                while True:
                    cmd_tokens = parser.get_command()
                    if cmd_tokens is None:
                        break
                    if not cmd_tokens:
                        continue

                    cmd_name = cmd_tokens[0].decode("utf-8", errors="replace").upper()
                    cmd_args = cmd_tokens[1:]

                    try:
                        registry.execute(cmd_name, cmd_args, context)
                        replayed_count += 1
                    except Exception:
                        # Continue replaying remaining valid commands
                        pass

        return replayed_count

    def rewrite(self, store: DataStore) -> int:
        """Rewrite/compact AOF by dumping current memory state as atomic commands."""
        temp_path = self.filepath.with_suffix(".tmp")
        commands_written = 0

        with open(temp_path, "wb") as f:
            for key in store.keys("*"):
                obj = store.get(key)
                if obj is None:
                    continue

                # 1. State reconstruction command
                if obj.data_type == DataType.STRING:
                    f.write(RespEncoder.encode_array(["SET", key, obj.value]))
                    commands_written += 1

                elif obj.data_type == DataType.LIST:
                    elements = list(obj.value)
                    if elements:
                        f.write(RespEncoder.encode_array(["RPUSH", key] + elements))
                        commands_written += 1

                elif obj.data_type == DataType.SET:
                    members = list(obj.value)
                    if members:
                        f.write(RespEncoder.encode_array(["SADD", key] + members))
                        commands_written += 1

                elif obj.data_type == DataType.HASH:
                    fields = []
                    for k, v in obj.value.items():
                        fields.extend([k, v])
                    if fields:
                        f.write(RespEncoder.encode_array(["HSET", key] + fields))
                        commands_written += 1

                elif obj.data_type == DataType.ZSET:
                    score_map, _ = obj.value
                    pairs = []
                    for m, score in score_map.items():
                        pairs.extend([str(score), m])
                    if pairs:
                        f.write(RespEncoder.encode_array(["ZADD", key] + pairs))
                        commands_written += 1

                # 2. Reconstruct TTL if set
                ttl = store.get_ttl(key)
                if ttl is not None and ttl > 0:
                    expire_at = time.time() + ttl
                    f.write(RespEncoder.encode_array(["EXPIREAT", key, str(expire_at)]))
                    commands_written += 1

        # Atomically replace old AOF with rewritten AOF
        self.close()
        temp_path.replace(self.filepath)
        self.open()
        return commands_written

    def get_status(self) -> Dict[str, Any]:
        """Return operational metrics for persistence telemetry."""
        size_bytes = self.filepath.stat().st_size if self.filepath.exists() else 0
        return {
            "enabled": self.enabled,
            "filepath": str(self.filepath),
            "fsync_policy": self.fsync_policy.value,
            "size_bytes": size_bytes,
            "writes_total": self._writes_total,
            "last_fsync_timestamp": self._last_fsync_time,
        }
