"""Server and key utility commands."""

from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.core.types import Role
from pyredis.protocol.types import SimpleString


def _to_str(val: Union[bytes, str]) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


@command("PING", min_args=0, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Ping the server")
def ping_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    if not args:
        return SimpleString("PONG")
    return args[0]


@command("ECHO", min_args=1, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Echo the given string")
def echo_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    return args[0]


@command("EXISTS", min_args=1, max_args=None, role=Role.READONLY, complexity="O(N)", is_mutation=False, description="Determine if keys exist")
def exists_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    count = 0
    for arg in args:
        if context.store.exists(_to_str(arg)):
            count += 1
    return count


@command("DEL", min_args=1, max_args=None, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Delete keys")
def del_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    deleted = 0
    for arg in args:
        if context.store.delete(_to_str(arg)):
            deleted += 1
    return deleted


@command("TYPE", min_args=1, max_args=1, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Determine the type stored at key")
def type_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    t = context.store.get_type(_to_str(args[0]))
    return SimpleString(t.value if t else "none")


@command("KEYS", min_args=1, max_args=1, role=Role.READONLY, complexity="O(N)", is_mutation=False, description="Find all keys matching the given pattern")
def keys_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[str]:
    pattern = _to_str(args[0])
    return context.store.keys(pattern)


@command("DBSIZE", min_args=0, max_args=0, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Return the number of keys in the database")
def dbsize_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    return context.store.dbsize()


@command("FLUSHDB", min_args=0, max_args=0, role=Role.OPERATOR, complexity="O(N)", is_mutation=True, description="Remove all keys from the current database")
def flushdb_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    context.store.flushdb()
    return SimpleString("OK")
