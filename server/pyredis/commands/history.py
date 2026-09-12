"""Key version history and time-travel commands."""

from typing import Any, List, Optional, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.types import Role
from pyredis.features.history import history_manager


@command("HISTORY", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(K)", is_mutation=False, description="View version history and revisions for key: HISTORY key")
def history_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[List[Union[str, int]]]:
    key = _to_str(args[0])
    revisions = history_manager.get_history(key)
    result = []
    for r in revisions:
        result.append([
            str(r["version"]),
            str(r["timestamp"]),
            r["data_type"],
            str(r["size_bytes"]),
            r["value_repr"][:60],
        ])
    return result


@command("GET.VERSION", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Retrieve snapshot of key at specific historical version: GET.VERSION key version")
def get_version_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[str]:
    key = _to_str(args[0])
    try:
        ver = int(_to_str(args[1]))
    except ValueError:
        return None

    rev = history_manager.get_revision(key, ver)
    if not rev:
        return None
    return rev["value_repr"]
