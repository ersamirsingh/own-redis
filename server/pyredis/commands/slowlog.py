"""SLOWLOG command handlers (SLOWLOG GET, SLOWLOG LEN, SLOWLOG RESET)."""

from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import Role
from pyredis.metrics.collector import metrics_collector
from pyredis.protocol.types import SimpleString


@command("SLOWLOG", min_args=1, max_args=2, role=Role.READONLY, complexity="O(N)", is_mutation=False, description="Inspect the slow query log")
def slowlog_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Any:
    collector = context.metrics if context.metrics is not None else metrics_collector
    subcommand = _to_str(args[0]).upper()

    if subcommand == "GET":
        count = 10
        if len(args) == 2:
            try:
                count = int(_to_str(args[1]))
            except ValueError:
                raise CommandError("ERR value is not an integer or out of range")
        entries = collector.get_slow_log(count)
        return [entry.to_resp() for entry in entries]

    elif subcommand == "LEN":
        return collector.slow_log_len()

    elif subcommand == "RESET":
        collector.slow_log_reset()
        return SimpleString("OK")

    else:
        raise CommandError(f"ERR unknown subcommand '{subcommand}'. Try SLOWLOG HELP.")
