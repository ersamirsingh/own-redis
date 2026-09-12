"""TTL and Expiration commands."""

import time
from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.types import Role


@command("EXPIRE", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Set a key's time to live in seconds")
def expire_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    try:
        seconds = float(_to_str(args[1]))
    except ValueError:
        return 0

    if not context.store.exists(key):
        return 0

    expire_at = time.time() + seconds
    context.store.set_ttl(key, expire_at)
    return 1


@command("PEXPIRE", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Set a key's time to live in milliseconds")
def pexpire_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    try:
        msec = float(_to_str(args[1]))
    except ValueError:
        return 0

    if not context.store.exists(key):
        return 0

    expire_at = time.time() + (msec / 1000.0)
    context.store.set_ttl(key, expire_at)
    return 1


@command("EXPIREAT", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Set the expiration for a key as a UNIX timestamp")
def expireat_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    try:
        timestamp = float(_to_str(args[1]))
    except ValueError:
        return 0

    if not context.store.exists(key):
        return 0

    context.store.set_ttl(key, timestamp)
    return 1


@command("PEXPIREAT", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Set the expiration for a key as a UNIX timestamp in milliseconds")
def pexpireat_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    try:
        msec_timestamp = float(_to_str(args[1]))
    except ValueError:
        return 0

    if not context.store.exists(key):
        return 0

    context.store.set_ttl(key, msec_timestamp / 1000.0)
    return 1


@command("TTL", min_args=1, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Get the time to live for a key in seconds")
def ttl_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    ttl_sec = context.store.get_ttl(key)
    if ttl_sec is None or ttl_sec == -2.0:
        return -2
    if ttl_sec == -1.0:
        return -1
    return int(ttl_sec)


@command("PTTL", min_args=1, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Get the time to live for a key in milliseconds")
def pttl_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    ttl_sec = context.store.get_ttl(key)
    if ttl_sec is None or ttl_sec == -2.0:
        return -2
    if ttl_sec == -1.0:
        return -1
    return int(ttl_sec * 1000.0)


@command("PERSIST", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Remove the expiration from a key")
def persist_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    return 1 if context.store.persist(key) else 0
