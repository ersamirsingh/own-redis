"""Unit tests for command execution, all 5 data structures, and RBAC."""

import pytest
from pyredis.commands import CommandContext, registry
from pyredis.core.exceptions import AuthError, CommandError, WrongTypeError
from pyredis.core.types import Role
from pyredis.protocol.types import SimpleString
from pyredis.storage import DataStore


@pytest.fixture
def ctx() -> CommandContext:
    return CommandContext(store=DataStore(), role=Role.ADMIN)


class TestStringCommands:
    def test_set_and_get(self, ctx: CommandContext) -> None:
        assert registry.execute("SET", ["name", "Samir"], ctx) == SimpleString("OK")
        assert registry.execute("GET", ["name"], ctx) == b"Samir"
        assert registry.execute("GET", ["nonexistent"], ctx) is None

    def test_set_nx_xx(self, ctx: CommandContext) -> None:
        assert registry.execute("SET", ["k", "v", "NX"], ctx) == SimpleString("OK")
        # Second NX should fail
        assert registry.execute("SET", ["k", "v2", "NX"], ctx) is None
        # XX should succeed
        assert registry.execute("SET", ["k", "v3", "XX"], ctx) == SimpleString("OK")
        assert registry.execute("GET", ["k"], ctx) == b"v3"

    def test_incr_decr_append(self, ctx: CommandContext) -> None:
        assert registry.execute("INCR", ["counter"], ctx) == 1
        assert registry.execute("INCR", ["counter"], ctx) == 2
        assert registry.execute("DECR", ["counter"], ctx) == 1
        assert registry.execute("APPEND", ["name", "Hello"], ctx) == 5
        assert registry.execute("APPEND", ["name", " World"], ctx) == 11
        assert registry.execute("GET", ["name"], ctx) == b"Hello World"


class TestListCommands:
    def test_lpush_rpush_lrange(self, ctx: CommandContext) -> None:
        assert registry.execute("RPUSH", ["mylist", "a", "b", "c"], ctx) == 3
        assert registry.execute("LPUSH", ["mylist", "first"], ctx) == 4
        # Range all
        assert registry.execute("LRANGE", ["mylist", 0, -1], ctx) == [
            b"first",
            b"a",
            b"b",
            b"c",
        ]
        # Pop
        assert registry.execute("LPOP", ["mylist"], ctx) == b"first"
        assert registry.execute("RPOP", ["mylist"], ctx) == b"c"
        assert registry.execute("LLEN", ["mylist"], ctx) == 2


class TestSetCommands:
    def test_sadd_srem_sismember(self, ctx: CommandContext) -> None:
        assert registry.execute("SADD", ["myset", "m1", "m2", "m3"], ctx) == 3
        assert registry.execute("SADD", ["myset", "m1"], ctx) == 0  # Duplicate
        assert registry.execute("SCARD", ["myset"], ctx) == 3
        assert registry.execute("SISMEMBER", ["myset", "m1"], ctx) == 1
        assert registry.execute("SISMEMBER", ["myset", "m99"], ctx) == 0
        assert registry.execute("SREM", ["myset", "m2"], ctx) == 1
        assert registry.execute("SCARD", ["myset"], ctx) == 2


class TestHashCommands:
    def test_hset_hget_hgetall(self, ctx: CommandContext) -> None:
        assert registry.execute("HSET", ["user:1", "name", "Alice", "role", "admin"], ctx) == 2
        assert registry.execute("HGET", ["user:1", "name"], ctx) == b"Alice"
        assert registry.execute("HEXISTS", ["user:1", "role"], ctx) == 1
        assert registry.execute("HLEN", ["user:1"], ctx) == 2
        all_fields = registry.execute("HGETALL", ["user:1"], ctx)
        assert len(all_fields) == 4  # 2 pairs = 4 items
        assert registry.execute("HDEL", ["user:1", "role"], ctx) == 1
        assert registry.execute("HLEN", ["user:1"], ctx) == 1


class TestZSetCommands:
    def test_zadd_zrange_zrank_zscore(self, ctx: CommandContext) -> None:
        assert registry.execute("ZADD", ["board", "100", "p1", "200", "p2", "50", "p3"], ctx) == 3
        # Sorted order: p3(50), p1(100), p2(200)
        assert registry.execute("ZRANK", ["board", "p3"], ctx) == 0
        assert registry.execute("ZRANK", ["board", "p1"], ctx) == 1
        assert registry.execute("ZRANK", ["board", "p2"], ctx) == 2
        assert registry.execute("ZSCORE", ["board", "p2"], ctx) == b"200.0"

        # ZRANGE with scores
        res = registry.execute("ZRANGE", ["board", 0, -1, "WITHSCORES"], ctx)
        assert res == [b"p3", b"50.0", b"p1", b"100.0", b"p2", b"200.0"]

        assert registry.execute("ZREM", ["board", "p1"], ctx) == 1
        assert registry.execute("ZCARD", ["board"], ctx) == 2


class TestRBACAndValidation:
    def test_readonly_user_blocked_on_mutations(self) -> None:
        store = DataStore()
        readonly_ctx = CommandContext(store=store, role=Role.READONLY)

        # Reads should succeed
        assert registry.execute("PING", [], readonly_ctx) == SimpleString("PONG")
        assert registry.execute("DBSIZE", [], readonly_ctx) == 0

        # Mutations should be blocked by RBAC
        with pytest.raises(AuthError):
            registry.execute("SET", ["k", "v"], readonly_ctx)

        with pytest.raises(AuthError):
            registry.execute("DEL", ["k"], readonly_ctx)

        with pytest.raises(AuthError):
            registry.execute("LPUSH", ["list", "val"], readonly_ctx)

    def test_arity_validation(self, ctx: CommandContext) -> None:
        with pytest.raises(CommandError):
            registry.execute("GET", [], ctx)  # Missing key arg

        with pytest.raises(CommandError):
            registry.execute("GET", ["k1", "k2"], ctx)  # Too many args
