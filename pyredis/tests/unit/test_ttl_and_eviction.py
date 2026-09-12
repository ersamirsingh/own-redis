"""Unit tests for TTL, Active Expiration, and Adaptive Eviction."""

import time
import pytest
from pyredis.commands import CommandContext, registry
from pyredis.core.exceptions import OutOfMemoryError
from pyredis.core.types import EvictionPolicy, Role
from pyredis.eviction.policy import EvictionManager
from pyredis.expiration.manager import ExpirationManager
from pyredis.storage.object import create_string
from pyredis.storage.store import DataStore


@pytest.fixture
def store() -> DataStore:
    return DataStore()


@pytest.fixture
def ctx(store: DataStore) -> CommandContext:
    return CommandContext(store=store, role=Role.ADMIN)


class TestTTLEngine:
    def test_expire_and_ttl_commands(self, ctx: CommandContext) -> None:
        registry.execute("SET", ["session", "abc"], ctx)
        assert registry.execute("TTL", ["session"], ctx) == -1  # No TTL

        # Set 10s TTL
        assert registry.execute("EXPIRE", ["session", "10"], ctx) == 1
        ttl = registry.execute("TTL", ["session"], ctx)
        assert 8 <= ttl <= 10

        # PTTL
        pttl = registry.execute("PTTL", ["session"], ctx)
        assert 8000 <= pttl <= 10000

        # Persist
        assert registry.execute("PERSIST", ["session"], ctx) == 1
        assert registry.execute("TTL", ["session"], ctx) == -1

    def test_lazy_expiration(self, ctx: CommandContext) -> None:
        registry.execute("SET", ["temp", "val"], ctx)
        # Expire in 0.05 seconds
        registry.execute("PEXPIRE", ["temp", "50"], ctx)
        assert registry.execute("GET", ["temp"], ctx) == b"val"

        time.sleep(0.06)
        # Should be lazily evicted on read
        assert registry.execute("GET", ["temp"], ctx) is None
        assert registry.execute("EXISTS", ["temp"], ctx) == 0

    def test_active_expiration_sweep(self, store: DataStore) -> None:
        exp_mgr = ExpirationManager(store)
        store.set("k1", create_string(b"v1"))
        store.set("k2", create_string(b"v2"))
        store.set("k3", create_string(b"v3"))

        # Set k1 and k2 to expire in past
        now = time.time()
        exp_mgr.set_expiration("k1", now - 1.0)
        exp_mgr.set_expiration("k2", now - 0.5)
        # k3 expires in future
        exp_mgr.set_expiration("k3", now + 100.0)

        swept = exp_mgr.sweep_now()
        assert swept == 2
        assert exp_mgr.expired_total == 2
        assert store.exists("k1") is False
        assert store.exists("k2") is False
        assert store.exists("k3") is True

    def test_ttl_metrics_distribution(self, store: DataStore) -> None:
        exp_mgr = ExpirationManager(store)
        now = time.time()
        store.set("short", create_string(b"a"))
        store.set("medium", create_string(b"b"))
        store.set("long", create_string(b"c"))
        store.set("not_tl", create_string(b"d"))

        exp_mgr.set_expiration("short", now + 5)
        exp_mgr.set_expiration("medium", now + 30)
        exp_mgr.set_expiration("long", now + 500)

        metrics = exp_mgr.get_metrics()
        assert metrics["keys_with_ttl"] == 3
        assert metrics["keys_without_ttl"] == 1
        assert metrics["distribution"]["under_10s"] == 1
        assert metrics["distribution"]["10s_to_1m"] == 1


class TestEvictionEngine:
    def test_lru_eviction(self, store: DataStore) -> None:
        evict_mgr = EvictionManager(store, policy=EvictionPolicy.ALLKEYS_LRU)
        store.set("k1", create_string(b"v1"))
        store.set("k2", create_string(b"v2"))
        store.set("k3", create_string(b"v3"))

        # Manually alter last_accessed_at
        store._data["k1"].last_accessed_at = 100.0
        store._data["k2"].last_accessed_at = 300.0
        store._data["k3"].last_accessed_at = 200.0

        # LRU should pick k1 (smallest access timestamp)
        assert evict_mgr.pick_eviction_candidate() == "k1"

    def test_lfu_eviction(self, store: DataStore) -> None:
        evict_mgr = EvictionManager(store, policy=EvictionPolicy.ALLKEYS_LFU)
        store.set("k1", create_string(b"v1"))
        store.set("k2", create_string(b"v2"))
        store.set("k3", create_string(b"v3"))

        store._data["k1"].access_count = 50
        store._data["k2"].access_count = 3  # Least accessed
        store._data["k3"].access_count = 20

        assert evict_mgr.pick_eviction_candidate() == "k2"

    def test_adaptive_eviction(self, store: DataStore) -> None:
        evict_mgr = EvictionManager(store, policy=EvictionPolicy.ADAPTIVE)
        store.set("frequent_hot", create_string(b"v1"))
        store.set("idle_cold", create_string(b"v2"))

        # Cold item has been idle for long and rarely touched
        store._data["frequent_hot"].last_accessed_at = time.monotonic()
        store._data["frequent_hot"].access_count = 100

        store._data["idle_cold"].last_accessed_at = time.monotonic() - 1000
        store._data["idle_cold"].access_count = 1

        # Adaptive score should heavily prioritize evicting the idle/cold key
        score_hot = evict_mgr.calculate_adaptive_score("frequent_hot")
        score_cold = evict_mgr.calculate_adaptive_score("idle_cold")
        assert score_cold > score_hot
        assert evict_mgr.pick_eviction_candidate() == "idle_cold"

    def test_noeviction_raises_oom(self, store: DataStore) -> None:
        evict_mgr = EvictionManager(store, max_memory=100, policy=EvictionPolicy.NOEVICTION)
        store.set("large_key", create_string(b"x" * 200))

        with pytest.raises(OutOfMemoryError):
            evict_mgr.evict_if_needed()

    def test_temperature_classification(self, store: DataStore) -> None:
        evict_mgr = EvictionManager(store)
        store.set("hot_key", create_string(b"a"))
        store.set("cold_key", create_string(b"b"))

        store._data["hot_key"].last_accessed_at = time.monotonic() - 5
        store._data["hot_key"].access_count = 10

        store._data["cold_key"].last_accessed_at = time.monotonic() - 500
        store._data["cold_key"].access_count = 1

        assert evict_mgr.classify_temperature("hot_key") == "HOT"
        assert evict_mgr.classify_temperature("cold_key") == "COLD"
