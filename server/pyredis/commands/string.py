"""String commands."""

import time
from typing import Any, List, Optional, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError, WrongTypeError
from pyredis.core.types import DataType, Role
from pyredis.protocol.types import SimpleString
from pyredis.storage.object import create_string


@command("SET", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Set the string value of a key")
def set_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[SimpleString]:
    key = _to_str(args[0])
    val = args[1]
    raw_bytes = val if isinstance(val, bytes) else val.encode("utf-8")

    expire_at: Optional[float] = None
    nx = False
    xx = False

    # Parse optional arguments: EX, PX, NX, XX
    idx = 2
    while idx < len(args):
        opt = _to_str(args[idx]).upper()
        if opt == "EX":
            if idx + 1 >= len(args):
                raise CommandError("syntax error")
            sec = float(_to_str(args[idx + 1]))
            expire_at = time.time() + sec
            idx += 2
        elif opt == "PX":
            if idx + 1 >= len(args):
                raise CommandError("syntax error")
            msec = float(_to_str(args[idx + 1]))
            expire_at = time.time() + (msec / 1000.0)
            idx += 2
        elif opt == "NX":
            nx = True
            idx += 1
        elif opt == "XX":
            xx = True
            idx += 1
        else:
            raise CommandError("syntax error")

    if nx and xx:
        raise CommandError("syntax error")

    key_exists = context.store.exists(key)
    if nx and key_exists:
        return None  # Nil response
    if xx and not key_exists:
        return None  # Nil response

    obj = create_string(raw_bytes)
    context.store.set(key, obj, expire_at=expire_at)
    return SimpleString("OK")


@command("GET", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the value of a key")
def get_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.STRING)
    if obj is None:
        return None
    val = obj.value
    return val if isinstance(val, bytes) else str(val).encode("utf-8")


@command("INCR", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Increment the integer value of a key by one")
def incr_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.STRING)
    if obj is None:
        obj = create_string(b"1")
        context.store.set(key, obj)
        return 1

    try:
        cur_str = _to_str(obj.value)
        cur_val = int(cur_str)
    except ValueError:
        raise CommandError("ERR value is not an integer or out of range")

    new_val = cur_val + 1
    obj.value = str(new_val).encode("utf-8")
    obj.update_size()
    return new_val


@command("DECR", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Decrement the integer value of a key by one")
def decr_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.STRING)
    if obj is None:
        obj = create_string(b"-1")
        context.store.set(key, obj)
        return -1

    try:
        cur_str = _to_str(obj.value)
        cur_val = int(cur_str)
    except ValueError:
        raise CommandError("ERR value is not an integer or out of range")

    new_val = cur_val - 1
    obj.value = str(new_val).encode("utf-8")
    obj.update_size()
    return new_val


@command("APPEND", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Append a value to a key")
def append_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    to_append = args[1] if isinstance(args[1], bytes) else args[1].encode("utf-8")
    obj = context.store.ensure_type(key, DataType.STRING)
    if obj is None:
        obj = create_string(to_append)
        context.store.set(key, obj)
        return len(to_append)

    val = obj.value if isinstance(obj.value, bytes) else str(obj.value).encode("utf-8")
    new_val = val + to_append
    obj.value = new_val
    obj.update_size()
    return len(new_val)


@command("MGET", min_args=1, max_args=None, role=Role.DEVELOPER, complexity="O(N)", is_mutation=False, description="Get the values of all the given keys")
def mget_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[Optional[bytes]]:
    result: List[Optional[bytes]] = []
    for arg in args:
        key = _to_str(arg)
        try:
            obj = context.store.ensure_type(key, DataType.STRING)
            if obj is None:
                result.append(None)
            else:
                val = obj.value
                result.append(val if isinstance(val, bytes) else str(val).encode("utf-8"))
        except WrongTypeError:
            result.append(None)
    return result


@command("MSET", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Set multiple keys to multiple values")
def mset_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    if len(args) % 2 != 0:
        raise CommandError("wrong number of arguments for 'mset' command")
    for i in range(0, len(args), 2):
        key = _to_str(args[i])
        val = args[i + 1]
        raw_bytes = val if isinstance(val, bytes) else val.encode("utf-8")
        context.store.set(key, create_string(raw_bytes))
    return SimpleString("OK")
