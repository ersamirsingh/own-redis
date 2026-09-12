"""Persistence command handlers (SAVE, BGSAVE, BGREWRITEAOF, LASTSAVE)."""

import asyncio
import time
from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.core.exceptions import CommandError
from pyredis.core.types import Role
from pyredis.protocol.types import SimpleString


@command("SAVE", min_args=0, max_args=0, role=Role.OPERATOR, complexity="O(N)", is_mutation=False, description="Synchronously save the dataset to disk")
def save_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    if context.snapshot is None:
        raise CommandError("ERR persistence snapshot engine is not configured")
    context.snapshot.save(context.store)
    return SimpleString("OK")


@command("BGSAVE", min_args=0, max_args=0, role=Role.OPERATOR, complexity="O(N)", is_mutation=False, description="Asynchronously save the dataset to disk")
def bgsave_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    if context.snapshot is None:
        raise CommandError("ERR persistence snapshot engine is not configured")
    if context.snapshot._is_saving:
        raise CommandError("ERR background save already in progress")

    # Launch background task
    asyncio.create_task(context.snapshot.bgsave(context.store))
    return SimpleString("Background saving started")


@command("BGREWRITEAOF", min_args=0, max_args=0, role=Role.OPERATOR, complexity="O(N)", is_mutation=False, description="Asynchronously rewrite the append-only file")
def bgrewriteaof_cmd(args: List[Union[bytes, str]], context: CommandContext) -> SimpleString:
    if context.aof is None:
        raise CommandError("ERR append-only file engine is not configured")

    asyncio.create_task(asyncio.to_thread(context.aof.rewrite, context.store))
    return SimpleString("Background append only file rewriting started")


@command("LASTSAVE", min_args=0, max_args=0, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Get the UNIX timestamp of the last successful save")
def lastsave_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    if context.snapshot is None or context.snapshot._last_save_time is None:
        return 0
    return int(context.snapshot._last_save_time)
