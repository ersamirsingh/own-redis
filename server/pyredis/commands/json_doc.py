"""JSON document commands and path traversal."""

import json
import re
from typing import Any, List, Optional, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import DataType, Role
from pyredis.events.bus import event_bus
from pyredis.events.types import Event, EventType
from pyredis.storage.object import create_json


def parse_json_path(path: str) -> List[Union[str, int]]:
    """Parse JSON path string into token list."""
    clean = path.strip()
    if clean.startswith("$"):
        clean = clean[1:]
    if clean.startswith("."):
        clean = clean[1:]
    if not clean:
        return []

    tokens: List[Union[str, int]] = []
    parts = re.findall(r'[^.\[\]]+|\[\d+\]', clean)
    for p in parts:
        if p.startswith("[") and p.endswith("]"):
            tokens.append(int(p[1:-1]))
        else:
            tokens.append(p)
    return tokens


def get_json_at_path(doc: Any, tokens: List[Union[str, int]]) -> Any:
    """Retrieve sub-value at path tokens."""
    curr = doc
    for tok in tokens:
        if isinstance(curr, dict) and isinstance(tok, str) and tok in curr:
            curr = curr[tok]
        elif isinstance(curr, list) and isinstance(tok, int) and 0 <= tok < len(curr):
            curr = curr[tok]
        else:
            return None
    return curr


def set_json_at_path(doc: Any, tokens: List[Union[str, int]], value: Any) -> Any:
    """Set value at path tokens. Modifies doc in-place or returns new root."""
    if not tokens:
        return value

    curr = doc
    for tok in tokens[:-1]:
        if isinstance(curr, dict):
            if tok not in curr or not isinstance(curr[tok], (dict, list)):
                curr[tok] = {}
            curr = curr[tok]
        elif isinstance(curr, list) and isinstance(tok, int):
            if 0 <= tok < len(curr):
                curr = curr[tok]
            else:
                raise CommandError(f"ERR Index out of bounds: {tok}")
        else:
            raise CommandError("ERR Cannot navigate non-container JSON element")

    last_tok = tokens[-1]
    if isinstance(curr, dict) and isinstance(last_tok, str):
        curr[last_tok] = value
    elif isinstance(curr, list) and isinstance(last_tok, int):
        if 0 <= last_tok < len(curr):
            curr[last_tok] = value
        elif last_tok == len(curr):
            curr.append(value)
        else:
            raise CommandError(f"ERR Index out of bounds: {last_tok}")
    else:
        raise CommandError("ERR Invalid container for target path")

    return doc


def del_json_at_path(doc: Any, tokens: List[Union[str, int]]) -> bool:
    """Delete element at path tokens. Returns True if deleted."""
    if not tokens:
        return False

    curr = doc
    for tok in tokens[:-1]:
        if isinstance(curr, dict) and isinstance(tok, str) and tok in curr:
            curr = curr[tok]
        elif isinstance(curr, list) and isinstance(tok, int) and 0 <= tok < len(curr):
            curr = curr[tok]
        else:
            return False

    last_tok = tokens[-1]
    if isinstance(curr, dict) and isinstance(last_tok, str) and last_tok in curr:
        del curr[last_tok]
        return True
    elif isinstance(curr, list) and isinstance(last_tok, int) and 0 <= last_tok < len(curr):
        del curr[last_tok]
        return True
    return False


@command("JSON.SET", min_args=3, max_args=3, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Set JSON value at path: JSON.SET key path json_string")
def json_set_cmd(args: List[Union[bytes, str]], context: CommandContext) -> str:
    key = _to_str(args[0])
    path = _to_str(args[1])
    raw_val = _to_str(args[2])

    try:
        parsed_val = json.loads(raw_val)
    except json.JSONDecodeError as e:
        raise CommandError(f"ERR Invalid JSON syntax: {e}")

    tokens = parse_json_path(path)

    if not tokens:
        # Overwrite/create root document
        context.store.set(key, create_json(parsed_val))
    else:
        obj = context.store.get(key)
        if obj is None:
            # Initialize empty dict and set path
            root: Any = {}
            set_json_at_path(root, tokens, parsed_val)
            context.store.set(key, create_json(root))
        else:
            context.store.ensure_type(key, DataType.JSON)
            obj.value = set_json_at_path(obj.value, tokens, parsed_val)
            obj.touch()
            obj.update_size()

    event_bus.publish(Event(
        type=EventType.KEY_UPDATED,
        key=key,
        actor=context.session_user,
        metadata={"data_type": "json", "path": path},
    ))
    return "OK"


@command("JSON.GET", min_args=1, max_args=2, role=Role.READONLY, complexity="O(N)", is_mutation=False, description="Get JSON document or sub-tree at path: JSON.GET key [path]")
def json_get_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[str]:
    key = _to_str(args[0])
    path = _to_str(args[1]) if len(args) > 1 else "."

    obj = context.store.get(key)
    if obj is None:
        return None

    context.store.ensure_type(key, DataType.JSON)
    tokens = parse_json_path(path)

    if not tokens:
        return json.dumps(obj.value)

    sub_val = get_json_at_path(obj.value, tokens)
    if sub_val is None:
        return None
    return json.dumps(sub_val)


@command("JSON.DEL", min_args=1, max_args=2, role=Role.DEVELOPER, complexity="O(N)", is_mutation=True, description="Delete JSON document or key at path: JSON.DEL key [path]")
def json_del_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    path = _to_str(args[1]) if len(args) > 1 else "."

    obj = context.store.get(key)
    if obj is None:
        return 0

    context.store.ensure_type(key, DataType.JSON)
    tokens = parse_json_path(path)

    if not tokens:
        # Delete entire key
        return context.store.delete(key)

    deleted = del_json_at_path(obj.value, tokens)
    if deleted:
        obj.touch()
        obj.update_size()
        event_bus.publish(Event(
            type=EventType.KEY_UPDATED,
            key=key,
            actor=context.session_user,
            metadata={"data_type": "json", "action": "JSON.DEL", "path": path},
        ))
        return 1
    return 0


@command("JSON.TYPE", min_args=1, max_args=2, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Report type of JSON element at path")
def json_type_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[str]:
    key = _to_str(args[0])
    path = _to_str(args[1]) if len(args) > 1 else "."

    obj = context.store.get(key)
    if obj is None:
        return None

    context.store.ensure_type(key, DataType.JSON)
    tokens = parse_json_path(path)
    val = get_json_at_path(obj.value, tokens) if tokens else obj.value

    if val is None:
        return "null" if (not tokens and obj.value is None) else None
    if isinstance(val, dict):
        return "object"
    if isinstance(val, list):
        return "array"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, (int, float)):
        return "number"
    if isinstance(val, str):
        return "string"
    return "unknown"


@command("JSON.ARRAPPEND", min_args=3, max_args=None, role=Role.DEVELOPER, complexity="O(M)", is_mutation=True, description="Append elements to array at path: JSON.ARRAPPEND key path json_value...")
def json_arrappend_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    path = _to_str(args[1])

    obj = context.store.get(key)
    if obj is None:
        return 0

    context.store.ensure_type(key, DataType.JSON)
    tokens = parse_json_path(path)
    target = get_json_at_path(obj.value, tokens) if tokens else obj.value

    if not isinstance(target, list):
        raise CommandError("ERR Path does not resolve to an array")

    for raw in args[2:]:
        parsed = json.loads(_to_str(raw))
        target.append(parsed)

    obj.touch()
    obj.update_size()
    return len(target)
