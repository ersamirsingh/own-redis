"""Hash commands."""

from typing import Any, Dict, List, Optional, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import DataType, Role
from pyredis.storage.object import create_hash


@command("HSET", min_args=3, max_args=None, role=Role.DEVELOPER, complexity="O(1) per field", is_mutation=True, description="Set the string value of a hash field")
def hset_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    field_args = args[1:]
    if len(field_args) % 2 != 0:
        raise CommandError("wrong number of arguments for 'hset' command")

    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        obj = create_hash()
        context.store.set(key, obj)

    hmap: Dict[bytes, bytes] = obj.value
    created = 0

    for i in range(0, len(field_args), 2):
        f = field_args[i] if isinstance(field_args[i], bytes) else field_args[i].encode("utf-8")
        v = field_args[i + 1] if isinstance(field_args[i + 1], bytes) else field_args[i + 1].encode("utf-8")
        if f not in hmap:
            created += 1
        hmap[f] = v

    obj.update_size()
    return created


@command("HGET", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the value of a hash field")
def hget_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return None

    hmap: Dict[bytes, bytes] = obj.value
    f = args[1] if isinstance(args[1], bytes) else args[1].encode("utf-8")
    return hmap.get(f)


@command("HDEL", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Delete one or more hash fields")
def hdel_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return 0

    hmap: Dict[bytes, bytes] = obj.value
    deleted = 0

    for arg in args[1:]:
        f = arg if isinstance(arg, bytes) else arg.encode("utf-8")
        if f in hmap:
            del hmap[f]
            deleted += 1

    obj.update_size()
    return deleted


@command("HGETALL", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(N)", is_mutation=False, description="Get all the fields and values in a hash")
def hgetall_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return []

    hmap: Dict[bytes, bytes] = obj.value
    result: List[bytes] = []
    for k, v in hmap.items():
        result.append(k)
        result.append(v)
    return result


@command("HEXISTS", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Determine if a hash field exists")
def hexists_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return 0

    hmap: Dict[bytes, bytes] = obj.value
    f = args[1] if isinstance(args[1], bytes) else args[1].encode("utf-8")
    return 1 if f in hmap else 0


@command("HLEN", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the number of fields in a hash")
def hlen_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return 0
    return len(obj.value)


@command("HKEYS", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(N)", is_mutation=False, description="Get all the fields in a hash")
def hkeys_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return []
    return list(obj.value.keys())


@command("HVALS", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(N)", is_mutation=False, description="Get all the values in a hash")
def hvals_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.HASH)
    if obj is None:
        return []
    return list(obj.value.values())
