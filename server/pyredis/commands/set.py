"""Set commands."""

from typing import Any, List, Set, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.types import DataType, Role
from pyredis.storage.object import create_set


@command("SADD", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(1) per member", is_mutation=True, description="Add one or more members to a set")
def sadd_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.SET)
    if obj is None:
        obj = create_set()
        context.store.set(key, obj)

    s: Set[bytes] = obj.value
    added = 0
    for arg in args[1:]:
        raw = arg if isinstance(arg, bytes) else arg.encode("utf-8")
        if raw not in s:
            s.add(raw)
            added += 1

    obj.update_size()
    return added


@command("SREM", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Remove one or more members from a set")
def srem_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.SET)
    if obj is None:
        return 0

    s: Set[bytes] = obj.value
    removed = 0
    for arg in args[1:]:
        raw = arg if isinstance(arg, bytes) else arg.encode("utf-8")
        if raw in s:
            s.remove(raw)
            removed += 1

    obj.update_size()
    return removed


@command("SISMEMBER", min_args=2, max_args=2, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Determine if a given value is a member of a set")
def sismember_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.SET)
    if obj is None:
        return 0

    s: Set[bytes] = obj.value
    raw = args[1] if isinstance(args[1], bytes) else args[1].encode("utf-8")
    return 1 if raw in s else 0


@command("SMEMBERS", min_args=1, max_args=1, role=Role.READONLY, complexity="O(N)", is_mutation=False, description="Get all the members in a set")
def smembers_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.SET)
    if obj is None:
        return []
    return list(obj.value)


@command("SCARD", min_args=1, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Get the number of members in a set")
def scard_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.SET)
    if obj is None:
        return 0
    return len(obj.value)
