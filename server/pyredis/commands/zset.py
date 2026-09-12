"""Sorted Set (ZSET) commands backed by SkipList and Dict."""

from typing import Any, Dict, List, Optional, Tuple, Union
from pyredis.commands.registry import CommandContext, command
from pyredis.commands.server import _to_str
from pyredis.core.exceptions import CommandError
from pyredis.core.types import DataType, Role
from pyredis.storage.object import create_zset
from pyredis.storage.skiplist import SkipList


@command("ZADD", min_args=3, max_args=None, role=Role.DEVELOPER, complexity="O(log(N)) per element", is_mutation=True, description="Add one or more members to a sorted set, or update its score")
def zadd_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    pair_args = args[1:]
    if len(pair_args) % 2 != 0:
        raise CommandError("wrong number of arguments for 'zadd' command")

    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        obj = create_zset()
        context.store.set(key, obj)

    score_map: Dict[str, float]
    sl: SkipList
    score_map, sl = obj.value
    added = 0

    for i in range(0, len(pair_args), 2):
        try:
            score = float(_to_str(pair_args[i]))
        except ValueError:
            raise CommandError("ERR value is not a valid float")
        member = _to_str(pair_args[i + 1])

        if member in score_map:
            old_score = score_map[member]
            if old_score != score:
                sl.delete(old_score, member)
                sl.insert(score, member)
                score_map[member] = score
        else:
            sl.insert(score, member)
            score_map[member] = score
            added += 1

    obj.update_size()
    return added


@command("ZRANGE", min_args=3, max_args=4, role=Role.DEVELOPER, complexity="O(log(N)+M)", is_mutation=False, description="Return a range of members in a sorted set, by index")
def zrange_cmd(args: List[Union[bytes, str]], context: CommandContext) -> List[bytes]:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        return []

    start = int(_to_str(args[1]))
    stop = int(_to_str(args[2]))
    withscores = False

    if len(args) == 4:
        if _to_str(args[3]).upper() == "WITHSCORES":
            withscores = True
        else:
            raise CommandError("syntax error")

    _, sl = obj.value
    elements = sl.get_range_by_rank(start, stop, reverse=False)

    result: List[bytes] = []
    for member, score in elements:
        result.append(member.encode("utf-8"))
        if withscores:
            result.append(str(score).encode("utf-8"))
    return result


@command("ZRANK", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(log(N))", is_mutation=False, description="Determine the index of a member in a sorted set")
def zrank_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[int]:
    key = _to_str(args[0])
    member = _to_str(args[1])
    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        return None

    score_map, sl = obj.value
    score = score_map.get(member)
    if score is None:
        return None

    return sl.get_rank(score, member)


@command("ZREM", min_args=2, max_args=None, role=Role.DEVELOPER, complexity="O(M*log(N))", is_mutation=True, description="Remove one or more members from a sorted set")
def zrem_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        return 0

    score_map, sl = obj.value
    removed = 0

    for arg in args[1:]:
        member = _to_str(arg)
        score = score_map.pop(member, None)
        if score is not None:
            sl.delete(score, member)
            removed += 1

    obj.update_size()
    return removed


@command("ZSCORE", min_args=2, max_args=2, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the score associated with the given member in a sorted set")
def zscore_cmd(args: List[Union[bytes, str]], context: CommandContext) -> Optional[bytes]:
    key = _to_str(args[0])
    member = _to_str(args[1])
    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        return None

    score_map, _ = obj.value
    score = score_map.get(member)
    if score is None:
        return None
    return str(score).encode("utf-8")


@command("ZCARD", min_args=1, max_args=1, role=Role.DEVELOPER, complexity="O(1)", is_mutation=False, description="Get the number of members in a sorted set")
def zcard_cmd(args: List[Union[bytes, str]], context: CommandContext) -> int:
    key = _to_str(args[0])
    obj = context.store.ensure_type(key, DataType.ZSET)
    if obj is None:
        return 0
    score_map, _ = obj.value
    return len(score_map)
