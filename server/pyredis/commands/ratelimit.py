"""Rate limiting commands."""

from typing import Any, List, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.types import Role
from pyredis.features.ratelimit import rate_limiter


@command("RATELIMIT.CHECK", min_args=3, max_args=4, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Check token bucket rate limit: key max_tokens refill_rate_per_sec [tokens_requested]")
def ratelimit_check_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[Union[int, str]]:
    key = _to_str(args[0])
    try:
        max_tokens = float(_to_str(args[1]))
        refill_rate = float(_to_str(args[2]))
        requested = float(_to_str(args[3])) if len(args) > 3 else 1.0
    except ValueError:
        return [0, "0.0", "0.0"]

    allowed, remaining, retry_ms = rate_limiter.check_token_bucket(
        key=key,
        max_tokens=max_tokens,
        refill_rate_per_sec=refill_rate,
        requested=requested,
    )

    return [
        1 if allowed else 0,
        str(remaining),
        str(retry_ms),
    ]


@command("RATELIMIT.RESET", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Reset rate limiter state for a key")
def ratelimit_reset_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    return 1 if rate_limiter.reset(key) else 0
