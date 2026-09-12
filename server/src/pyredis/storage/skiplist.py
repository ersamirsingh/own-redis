"""Skip List implementation for Sorted Set (ZSET).

A probabilistic alternative to balanced trees, featuring multiple levels of forward pointers
with span annotations to provide O(log N) insertion, deletion, score lookup, and rank queries.
"""

import random
from typing import List, Optional, Tuple

MAX_LEVEL = 32
P = 0.25  # Redis uses 0.25 for memory efficiency


class SkipListNode:
    """A single node within the Skip List."""

    __slots__ = ("member", "score", "forward", "span", "backward")

    def __init__(self, level: int, score: float, member: str) -> None:
        self.score: float = score
        self.member: str = member
        # forward[i] is pointer to next node at level i
        self.forward: List[Optional["SkipListNode"]] = [None] * level
        # span[i] is distance (number of nodes) to forward[i]
        self.span: List[int] = [0] * level
        self.backward: Optional["SkipListNode"] = None


class SkipList:
    """Skip list supporting O(log N) operations with rank tracking."""

    def __init__(self) -> None:
        self.header = SkipListNode(MAX_LEVEL, 0.0, "")
        self.tail: Optional[SkipListNode] = None
        self.length: int = 0
        self.level: int = 1

    def _random_level(self) -> int:
        """Generate random level using geometric distribution."""
        lvl = 1
        while (random.random() < P) and (lvl < MAX_LEVEL):
            lvl += 1
        return lvl

    def insert(self, score: float, member: str) -> SkipListNode:
        """Insert a (score, member) into the skip list. Assumes member not present."""
        update: List[Optional[SkipListNode]] = [None] * MAX_LEVEL
        rank: List[int] = [0] * MAX_LEVEL
        x = self.header

        for i in range(self.level - 1, -1, -1):
            # Store rank of x at level i
            rank[i] = rank[i + 1] if i < self.level - 1 else 0
            while x.forward[i] and (
                x.forward[i].score < score
                or (x.forward[i].score == score and x.forward[i].member < member)
            ):
                rank[i] += x.span[i]
                x = x.forward[i]
            update[i] = x

        lvl = self._random_level()
        if lvl > self.level:
            for i in range(self.level, lvl):
                rank[i] = 0
                update[i] = self.header
                update[i].span[i] = self.length
            self.level = lvl

        x = SkipListNode(lvl, score, member)
        for i in range(lvl):
            x.forward[i] = update[i].forward[i]
            update[i].forward[i] = x

            # Update span
            x.span[i] = update[i].span[i] - (rank[0] - rank[i])
            update[i].span[i] = (rank[0] - rank[i]) + 1

        # Increment span for untouched levels above lvl
        for i in range(lvl, self.level):
            update[i].span[i] += 1

        x.backward = update[0] if update[0] != self.header else None
        if x.forward[0]:
            x.forward[0].backward = x
        else:
            self.tail = x

        self.length += 1
        return x

    def delete(self, score: float, member: str) -> bool:
        """Remove a node by score and member. Returns True if deleted."""
        update: List[Optional[SkipListNode]] = [None] * MAX_LEVEL
        x = self.header

        for i in range(self.level - 1, -1, -1):
            while x.forward[i] and (
                x.forward[i].score < score
                or (x.forward[i].score == score and x.forward[i].member < member)
            ):
                x = x.forward[i]
            update[i] = x

        target = x.forward[0]
        if target and target.score == score and target.member == member:
            self._delete_node(target, update)
            return True
        return False

    def _delete_node(self, x: SkipListNode, update: List[Optional[SkipListNode]]) -> None:
        """Internal helper to unlink node x and fix spans."""
        for i in range(self.level):
            if update[i].forward[i] == x:
                update[i].span[i] += x.span[i] - 1
                update[i].forward[i] = x.forward[i]
            else:
                update[i].span[i] -= 1

        if x.forward[0]:
            x.forward[0].backward = x.backward
        else:
            self.tail = x.backward

        while self.level > 1 and self.header.forward[self.level - 1] is None:
            self.level -= 1

        self.length -= 1

    def get_rank(self, score: float, member: str) -> Optional[int]:
        """Find 0-indexed rank of member. Returns None if not found."""
        rank = 0
        x = self.header
        for i in range(self.level - 1, -1, -1):
            while x.forward[i] and (
                x.forward[i].score < score
                or (x.forward[i].score == score and x.forward[i].member <= member)
            ):
                rank += x.span[i]
                x = x.forward[i]

        if x and x.member == member:
            return rank - 1  # 0-indexed
        return None

    def get_range_by_rank(
        self, start: int, stop: int, reverse: bool = False
    ) -> List[Tuple[str, float]]:
        """Retrieve [start, stop] inclusive slice (0-indexed). Supports negative indices."""
        if self.length == 0:
            return []

        # Convert negative indices
        if start < 0:
            start = self.length + start
        if stop < 0:
            stop = self.length + stop

        start = max(0, start)
        stop = min(self.length - 1, stop)
        if start > stop or start >= self.length:
            return []

        if not reverse:
            # Traversal forward: locate node at rank start
            traversed = 0
            x = self.header
            for i in range(self.level - 1, -1, -1):
                while x.forward[i] and (traversed + x.span[i] <= start + 1):
                    traversed += x.span[i]
                    x = x.forward[i]

            result: List[Tuple[str, float]] = []
            count = stop - start + 1
            while x and count > 0:
                result.append((x.member, x.score))
                x = x.forward[0]
                count -= 1
            return result
        else:
            # For reverse range: start is relative to highest score
            # Convert to forward rank: rev_start -> index (length - 1 - start)
            f_start = self.length - 1 - start
            f_stop = self.length - 1 - stop
            # We want nodes from f_start down to f_stop
            # Locate node at forward rank f_start
            traversed = 0
            x = self.header
            for i in range(self.level - 1, -1, -1):
                while x.forward[i] and (traversed + x.span[i] <= f_start + 1):
                    traversed += x.span[i]
                    x = x.forward[i]

            result = []
            count = start - stop + 1 if start >= stop else (stop - start + 1)
            while x and len(result) < count:
                result.append((x.member, x.score))
                x = x.backward
            return result
