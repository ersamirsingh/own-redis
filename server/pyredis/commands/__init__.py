"""PyRedis command system and registry."""

from pyredis.commands.registry import (
    CommandContext,
    CommandDefinition,
    CommandRegistry,
    command,
    registry,
)

# Import command modules to trigger decorator registrations
import pyredis.commands.server  # noqa: F401
import pyredis.commands.string  # noqa: F401
import pyredis.commands.list  # noqa: F401
import pyredis.commands.set  # noqa: F401
import pyredis.commands.hash  # noqa: F401
import pyredis.commands.zset  # noqa: F401
import pyredis.commands.ttl  # noqa: F401
import pyredis.commands.persistence  # noqa: F401
import pyredis.commands.slowlog  # noqa: F401
import pyredis.commands.lock  # noqa: F401
import pyredis.commands.ratelimit  # noqa: F401
import pyredis.commands.json_doc  # noqa: F401
import pyredis.commands.history  # noqa: F401
import pyredis.commands.memory  # noqa: F401

__all__ = [
    "registry",
    "command",
    "CommandRegistry",
    "CommandDefinition",
    "CommandContext",
]
