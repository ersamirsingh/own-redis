"""Unit tests for AOF and Snapshot persistence engines."""

import time
from pathlib import Path
import pytest
from pyredis.commands import CommandContext, registry
from pyredis.core.types import DataType, FsyncPolicy, Role
from pyredis.persistence.aof import AofEngine
from pyredis.persistence.snapshot import SnapshotEngine
from pyredis.protocol.types import SimpleString
from pyredis.storage import (
    DataStore,
    create_hash,
    create_list,
    create_set,
    create_string,
    create_zset,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestAofEngine:
    def test_aof_append_and_replay(self, temp_dir: Path) -> None:
        aof_file = temp_dir / "test.aof"
        engine = AofEngine(filepath=str(aof_file), fsync_policy=FsyncPolicy.ALWAYS)
        engine.open()

        # Append commands
        engine.append("SET", ["app", "pyredis"])
        engine.append("LPUSH", ["items", "v1", "v2"])
        engine.append("HSET", ["user:1", "name", "Alice"])
        engine.close()

        assert aof_file.exists()
        assert aof_file.stat().st_size > 0

        # Replay into fresh store
        fresh_store = DataStore()
        replayed = engine.replay(fresh_store, registry)
        assert replayed == 3

        # Verify state
        assert fresh_store.get("app").value == b"pyredis"
        assert list(fresh_store.get("items").value) == [b"v2", b"v1"]
        assert fresh_store.get("user:1").value == {b"name": b"Alice"}

    def test_aof_rewrite(self, temp_dir: Path) -> None:
        aof_file = temp_dir / "test_rewrite.aof"
        engine = AofEngine(filepath=str(aof_file), fsync_policy=FsyncPolicy.NO)
        engine.open()

        store = DataStore()
        store.set("counter", create_string(b"100"))
        store.set("tags", create_set({b"fast", b"redis"}))

        rewritten_count = engine.rewrite(store)
        assert rewritten_count == 2
        engine.close()

        # Replay rewritten AOF
        fresh_store = DataStore()
        engine.replay(fresh_store, registry)
        assert fresh_store.get("counter").value == b"100"
        assert fresh_store.get("tags").value == {b"fast", b"redis"}


class TestSnapshotEngine:
    def test_snapshot_save_and_load_all_types(self, temp_dir: Path) -> None:
        rdb_file = temp_dir / "dump.rdb"
        snapshot = SnapshotEngine(filepath=str(rdb_file))

        store = DataStore()
        # 1. String
        store.set("str", create_string(b"hello"))
        # 2. List
        store.set("list", create_list([b"a", b"b"]))
        # 3. Set
        store.set("set", create_set({b"x", b"y"}))
        # 4. Hash
        store.set("hash", create_hash({b"f1": b"v1"}))
        # 5. ZSet
        z_obj = create_zset()
        score_map, sl = z_obj.value
        score_map["p1"] = 10.5
        sl.insert(10.5, "p1")
        store.set("zset", z_obj)

        # Set TTL on one key
        store.set_ttl("str", time.time() + 3600)

        keys_saved = snapshot.save(store)
        assert keys_saved == 5
        assert rdb_file.exists()

        # Restore into empty store
        restored_store = DataStore()
        restored_count = snapshot.load(restored_store)
        assert restored_count == 5

        # Assert data integrity
        assert restored_store.get("str").value == b"hello"
        assert restored_store.get_ttl("str") > 3500
        assert list(restored_store.get("list").value) == [b"a", b"b"]
        assert restored_store.get("set").value == {b"x", b"y"}
        assert restored_store.get("hash").value == {b"f1": b"v1"}
        r_z_map, r_sl = restored_store.get("zset").value
        assert r_z_map["p1"] == 10.5
        assert r_sl.get_rank(10.5, "p1") == 0

    @pytest.mark.asyncio
    async def test_bgsave_async(self, temp_dir: Path) -> None:
        rdb_file = temp_dir / "bgdump.rdb"
        snapshot = SnapshotEngine(filepath=str(rdb_file))
        store = DataStore()
        store.set("k", create_string(b"v"))

        count = await snapshot.bgsave(store)
        assert count == 1
        assert rdb_file.exists()
        assert snapshot._last_save_key_count == 1


class TestPersistenceCommands:
    def test_save_and_lastsave(self, temp_dir: Path) -> None:
        rdb_file = temp_dir / "cmd_dump.rdb"
        snapshot = SnapshotEngine(filepath=str(rdb_file))
        store = DataStore()
        store.set("sample", create_string(b"data"))

        ctx = CommandContext(store=store, role=Role.ADMIN, snapshot=snapshot)
        assert registry.execute("SAVE", [], ctx) == SimpleString("OK")
        assert rdb_file.exists()
        lastsave = registry.execute("LASTSAVE", [], ctx)
        assert lastsave > 0
