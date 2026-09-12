"""Semantic memory and vector search commands."""

import json
from typing import Any, List, Optional, Union
from pyredis.ai.memory import semantic_memory
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import Role


@command("MEMORY.ADD", min_args=2, max_args=3, role=Role.DEVELOPER, complexity="O(D)", is_mutation=True, description="Add text to semantic memory: MEMORY.ADD id text [metadata_json]")
def memory_add_cmd(args: List[Union[bytes, str]], context: CommandContext) -> str:
    entry_id = _to_str(args[0])
    text = _to_str(args[1])
    metadata = {}
    if len(args) > 2:
        try:
            metadata = json.loads(_to_str(args[2]))
        except json.JSONDecodeError as e:
            raise CommandError(f"ERR Invalid metadata JSON: {e}")

    semantic_memory.add(text=text, id=entry_id, metadata=metadata)
    return "OK"


@command("MEMORY.SEARCH", min_args=1, max_args=3, role=Role.READONLY, complexity="O(N*D)", is_mutation=False, description="Search semantic memory by cosine vector similarity: MEMORY.SEARCH query [top_k] [min_score]")
def memory_search_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[List[Union[str, float]]]:
    query = _to_str(args[0])
    top_k = 5
    min_score = 0.0

    if len(args) > 1:
        try:
            top_k = int(_to_str(args[1]))
        except ValueError:
            pass

    if len(args) > 2:
        try:
            min_score = float(_to_str(args[2]))
        except ValueError:
            pass

    results = semantic_memory.search(query=query, top_k=top_k, min_score=min_score)
    output = []
    for r in results:
        output.append([
            r["id"],
            str(r["score"]),
            r["text"],
            json.dumps(r.get("metadata", {})),
        ])
    return output


@command("MEMORY.DEL", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=True, description="Delete vector record from semantic memory: MEMORY.DEL id")
def memory_del_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    entry_id = _to_str(args[0])
    deleted = semantic_memory.delete(entry_id)
    return 1 if deleted else 0


@command("MEMORY.COUNT", min_args=0, max_args=0, role=Role.READONLY, complexity="O(1)", is_mutation=False, description="Get total count of semantic memory vector entries")
def memory_count_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    return semantic_memory.count()
