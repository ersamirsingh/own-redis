"""Distributed Locking commands."""

from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.types import Role
from pyredis.features.lock import lock_manager


@command("LOCK", min_args=2, max_args=3, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Acquire a distributed lock on key with owner token and optional ttl_ms")
def lock_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    owner = _to_str(args[1])
    ttl_ms = 30000
    if len(args) > 2:
        try:
            ttl_ms = int(_to_str(args[2]))
        except ValueError:
            pass

    acquired = lock_manager.acquire(key, owner, ttl_ms=ttl_ms)
    return 1 if acquired else 0


@command("UNLOCK", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Release a distributed lock if caller is the verified owner")
def unlock_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    owner = _to_str(args[1])
    released = lock_manager.release(key, owner)
    return 1 if released else 0


@command("LOCK.EXTEND", min_args=3, max_args=3, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Extend active lock lease duration")
def lock_extend_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    owner = _to_str(args[1])
    try:
        ttl_ms = int(_to_str(args[2]))
    except ValueError:
        return 0

    extended = lock_manager.extend(key, owner, ttl_ms)
    return 1 if extended else 0


@command("LOCK.INFO", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get metadata and remaining TTL for active lock")
def lock_info_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    key = _to_str(args[0])
    info = lock_manager.info(key)
    if not info:
        return None
    return [
        "owner", info["owner"],
        "ttl_remaining_ms", str(info["ttl_remaining_ms"]),
        "acquired_at", str(info["acquired_at"]),
    ]
