"""Unit tests for Phase 10: Distributed Locks, Rate Limiter, JSON Documents, and Key Versioning."""

import json
import time
import pytest
from pyredis.api.app import create_app
from pyredis.auth.models import UserCreate
from pyredis.auth.repository import user_repo
from pyredis.auth.security import create_access_token
from pyredis.commands.registry import CommandContext, registry
from pyredis.core.types import Role
from pyredis.features.history import history_manager
from pyredis.features.lock import lock_manager
from pyredis.features.ratelimit import rate_limiter
from pyredis.storage.store import DataStore
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_features():
    lock_manager.clear()
    rate_limiter.clear()
    history_manager.clear()
    yield
    lock_manager.clear()
    rate_limiter.clear()
    history_manager.clear()


@pytest.fixture
def test_ctx():
    store = DataStore()
    context = CommandContext(store=store, role=Role.ADMIN, session_user="admin@pyredis.io")
    return {"store": store, "context": context}


class TestDistributedLock:
    def test_lock_acquire_and_release(self, test_ctx):
        context = test_ctx["context"]
        # Owner 1 acquires lock
        res = registry.execute("LOCK", ["res_100", "worker_A", "10000"], context)
        assert res == 1

        # Owner 2 tries to acquire same lock -> fails
        res2 = registry.execute("LOCK", ["res_100", "worker_B", "10000"], context)
        assert res2 == 0

        # Owner 1 re-entrant acquisition -> succeeds
        res_reentrant = registry.execute("LOCK", ["res_100", "worker_A", "15000"], context)
        assert res_reentrant == 1

        # Lock info
        info = registry.execute("LOCK.INFO", ["res_100"], context)
        assert info[1] == "worker_A"

        # Extend lock
        res_ext = registry.execute("LOCK.EXTEND", ["res_100", "worker_A", "20000"], context)
        assert res_ext == 1

        # Owner 2 tries to unlock -> fails
        res_fail_unlock = registry.execute("UNLOCK", ["res_100", "worker_B"], context)
        assert res_fail_unlock == 0

        # Owner 1 unlocks -> succeeds
        res_unlock = registry.execute("UNLOCK", ["res_100", "worker_A"], context)
        assert res_unlock == 1

        # Now worker B can acquire
        res_b = registry.execute("LOCK", ["res_100", "worker_B"], context)
        assert res_b == 1

    def test_lock_lease_expiry(self, test_ctx):
        context = test_ctx["context"]
        # Lock with very short 50ms TTL
        assert registry.execute("LOCK", ["res_temp", "worker_A", "50"], context) == 1
        time.sleep(0.06)
        # Lock should now be expired and available for worker B
        assert registry.execute("LOCK", ["res_temp", "worker_B", "5000"], context) == 1


class TestRateLimiter:
    def test_token_bucket_rate_limiting(self, test_ctx):
        context = test_ctx["context"]
        # Capacity 3 tokens, 1 refill/sec
        # 1. First 3 requests succeed
        for _ in range(3):
            res = registry.execute("RATELIMIT.CHECK", ["client_ip", "3", "1", "1"], context)
            assert res[0] == 1

        # 2. 4th request rejected (bucket empty)
        res_rejected = registry.execute("RATELIMIT.CHECK", ["client_ip", "3", "1", "1"], context)
        assert res_rejected[0] == 0
        assert float(res_rejected[2]) > 0  # Retry after ms

        # 3. Reset rate limit
        res_reset = registry.execute("RATELIMIT.RESET", ["client_ip"], context)
        assert res_reset == 1

        # 4. Immediate request allowed again
        res_allowed = registry.execute("RATELIMIT.CHECK", ["client_ip", "3", "1", "1"], context)
        assert res_allowed[0] == 1


class TestJsonDocuments:
    def test_json_set_get_path(self, test_ctx):
        context = test_ctx["context"]
        doc = {
            "name": "PyRedis",
            "version": 1.0,
            "config": {"shards": 4, "cluster": True},
            "tags": ["cache", "in-memory"],
        }
        # 1. Set root JSON
        res = registry.execute("JSON.SET", ["doc:1", ".", json.dumps(doc)], context)
        assert res == "OK"

        # 2. Get root JSON
        got = registry.execute("JSON.GET", ["doc:1"], context)
        assert json.loads(got)["name"] == "PyRedis"

        # 3. Get nested subpath
        name_sub = registry.execute("JSON.GET", ["doc:1", ".name"], context)
        assert json.loads(name_sub) == "PyRedis"

        shards = registry.execute("JSON.GET", ["doc:1", ".config.shards"], context)
        assert json.loads(shards) == 4

        tag0 = registry.execute("JSON.GET", ["doc:1", ".tags[0]"], context)
        assert json.loads(tag0) == "cache"

        # 4. Mutate nested subpath
        registry.execute("JSON.SET", ["doc:1", ".config.shards", "8"], context)
        shards_updated = registry.execute("JSON.GET", ["doc:1", ".config.shards"], context)
        assert json.loads(shards_updated) == 8

        # 5. Check type
        assert registry.execute("JSON.TYPE", ["doc:1", ".tags"], context) == "array"
        assert registry.execute("JSON.TYPE", ["doc:1", ".config"], context) == "object"

        # 6. Append to array
        new_len = registry.execute("JSON.ARRAPPEND", ["doc:1", ".tags", '"fast"'], context)
        assert new_len == 3

        # 7. Delete nested property
        del_res = registry.execute("JSON.DEL", ["doc:1", ".tags[0]"], context)
        assert del_res == 1

        # 8. Delete whole document
        assert registry.execute("JSON.DEL", ["doc:1"], context) == 1
        assert registry.execute("JSON.GET", ["doc:1"], context) is None


class TestKeyVersioningAndApi:
    def test_key_history_tracking(self, test_ctx):
        context = test_ctx["context"]
        # Mutate key multiple times
        registry.execute("SET", ["tracked_key", "version_1"], context)
        registry.execute("SET", ["tracked_key", "version_2"], context)
        registry.execute("SET", ["tracked_key", "version_3"], context)

        history = registry.execute("HISTORY", ["tracked_key"], context)
        assert len(history) == 3
        # Newest revision is first in HISTORY
        assert history[0][0] == "3"

        # Time travel query
        v1_val = registry.execute("GET.VERSION", ["tracked_key", "1"], context)
        assert "version_1" in v1_val

        v2_val = registry.execute("GET.VERSION", ["tracked_key", "2"], context)
        assert "version_2" in v2_val

    def test_locks_and_keys_api_endpoints(self):
        store = DataStore()
        app = create_app(store=store)
        client = TestClient(app)

        user_repo.clear()
        admin = user_repo.create_user(
            UserCreate(email="advadmin@pyredis.io", name="Adv Admin", password="AdminSecure123!"),
            force_role=Role.ADMIN,
        )
        token = create_access_token(admin.id, admin.email, admin.role)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Acquire lock via manager
        lock_manager.acquire("api_resource_1", "worker_99", 60000)

        # 2. List locks via REST
        res = client.get("/api/locks", headers=headers)
        assert res.status_code == 200
        locks = res.json()
        assert len(locks) >= 1
        assert any(l["key"] == "api_resource_1" for l in locks)

        # 3. Force release lock via REST
        rel_res = client.post("/api/locks/force-release", json={"key": "api_resource_1"}, headers=headers)
        assert rel_res.status_code == 200

        # 4. Create JSON key via /api/keys
        json_payload = {
            "key": "app:settings",
            "type": "json",
            "value": {"theme": "dark", "notifications": True},
        }
        create_res = client.post("/api/keys", json=json_payload, headers=headers)
        assert create_res.status_code in (200, 201)

        # 5. Get key details
        detail_res = client.get("/api/keys/app:settings", headers=headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["value"]["theme"] == "dark"

        # 6. Check history endpoint
        hist_res = client.get("/api/keys/app:settings/history", headers=headers)
        assert hist_res.status_code == 200
        assert len(hist_res.json()) >= 1
