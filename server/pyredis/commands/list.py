"""List commands."""

from collections import deque
from typing import Any, List, Optional, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import DataType, Role
from pyredis.storage.object import create_list


@command("LPUSH", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(1) per element", is_mutation=True, description="Prepend one or multiple elements to a list")
def lpush_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        obj = create_list()
        context.store.set(key, obj)

    dq: deque = obj.value
    # Redis LPUSH prepends elements one by one in order
    for elem in args[1:]:
        raw = elem if isinstance(elem, bytes) else elem.encode("utf-8")
        dq.appendleft(raw)

    obj.update_size()
    return len(dq)


@command("RPUSH", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(1) per element", is_mutation=True, description="Append one or multiple elements to a list")
def rpush_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        obj = create_list()
        context.store.set(key, obj)

    dq: deque = obj.value
    for elem in args[1:]:
        raw = elem if isinstance(elem, bytes) else elem.encode("utf-8")
        dq.append(raw)

    obj.update_size()
    return len(dq)


@command("LPOP", min_args=1, max_args=2, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Remove and get the first elements in a list")
def lpop_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        return None

    dq: deque = obj.value
    if not dq:
        return None

    has_count = len(args) == 2
    if not has_count:
        val = dq.popleft()
        obj.update_size()
        return val

    count = int(_to_str(args[1]))
    if count < 0:
        raise CommandError("ERR value is out of range, must be positive")

    result = []
    for _ in range(min(count, len(dq))):
        result.append(dq.popleft())
    obj.update_size()
    return result


@command("RPOP", min_args=1, max_args=2, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Remove and get the last elements in a list")
def rpop_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        return None

    dq: deque = obj.value
    if not dq:
        return None

    has_count = len(args) == 2
    if not has_count:
        val = dq.pop()
        obj.update_size()
        return val

    count = int(_to_str(args[1]))
    if count < 0:
        raise CommandError("ERR value is out of range, must be positive")

    result = []
    for _ in range(min(count, len(dq))):
        result.append(dq.pop())
    obj.update_size()
    return result


@command("LRANGE", min_args=3, max_args=3, role=Role.DEVELOPER, complexity="O(S+N)", is_mutation=False, description="Get a range of elements from a list")
def lrange_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        return []

    dq: deque = obj.value
    length = len(dq)
    if length == 0:
        return []

    start = int(_to_str(args[1]))
    stop = int(_to_str(args[2]))

    if start < 0:
        start = length + start
    if stop < 0:
        stop = length + stop

    start = max(0, start)
    stop = min(length - 1, stop)

    if start > stop or start >= length:
        return []

    as_list = list(dq)
    return as_list[start : stop + 1]


@command("LLEN", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the length of a list")
def llen_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.LIST)
    if obj is None:
        return 0
    return len(obj.value)
