"""Unit tests for SkipList and DataStore."""

import pytest
from pyredis.core.exceptions import WrongTypeError
from pyredis.core.types import DataType
from pyredis.storage import (
    DataStore,
    SkipList,
    create_hash,
    create_list,
    create_set,
    create_string,
    create_zset,
)


class TestSkipList:
    """Test SkipList rank, range, and deletion logic."""

    def test_insert_and_rank(self) -> None:
        sl = SkipList()
        sl.insert(10.0, "alice")
        sl.insert(20.0, "bob")
        sl.insert(15.0, "charlie")
        sl.insert(5.0, "david")

        assert sl.length == 4
        # Sorted order: david (5), alice (10), charlie (15), bob (20)
        assert sl.get_rank(5.0, "david") == 0
        assert sl.get_rank(10.0, "alice") == 1
        assert sl.get_rank(15.0, "charlie") == 2
        assert sl.get_rank(20.0, "bob") == 3
        assert sl.get_rank(99.0, "missing") is None

    def test_get_range_by_rank(self) -> None:
        sl = SkipList()
        sl.insert(10.0, "alice")
        sl.insert(20.0, "bob")
        sl.insert(15.0, "charlie")

        # Range 0 to 1
        r = sl.get_range_by_rank(0, 1)
        assert r == [("alice", 10.0), ("charlie", 15.0)]

        # Range all
        all_items = sl.get_range_by_rank(0, -1)
        assert all_items == [("alice", 10.0), ("charlie", 15.0), ("bob", 20.0)]

    def test_delete(self) -> None:
        sl = SkipList()
        sl.insert(10.0, "alice")
        sl.insert(20.0, "bob")

        assert sl.delete(10.0, "alice") is True
        assert sl.length == 1
        assert sl.delete(99.0, "nonexistent") is False
        assert sl.get_rank(20.0, "bob") == 0


class TestDataStore:
    """Test DataStore CRUD, type checking, and memory tracking."""

    def test_set_and_get(self) -> None:
        store = DataStore()
        obj = create_string(b"hello")
        store.set("greeting", obj)

        res = store.get("greeting")
        assert res is not None
        assert res.value == b"hello"
        assert res.data_type == DataType.STRING

    def test_ensure_type_raises_wrong_type(self) -> None:
        store = DataStore()
        store.set("str_key", create_string(b"text"))

        with pytest.raises(WrongTypeError):
            store.ensure_type("str_key", DataType.LIST)

    def test_delete_and_exists(self) -> None:
        store = DataStore()
        store.set("k1", create_string(b"v1"))
        assert store.exists("k1") is True
        assert store.delete("k1") is True
        assert store.exists("k1") is False
        assert store.delete("k1") is False

    def test_keys_and_dbsize(self) -> None:
        store = DataStore()
        store.set("user:1", create_string(b"a"))
        store.set("user:2", create_string(b"b"))
        store.set("item:1", create_string(b"c"))

        assert store.dbsize() == 3
        user_keys = store.keys("user:*")
        assert set(user_keys) == {"user:1", "user:2"}
        all_keys = store.keys("*")
        assert len(all_keys) == 3

    def test_flushdb(self) -> None:
        store = DataStore()
        store.set("k1", create_string(b"v1"))
        store.flushdb()
        assert store.dbsize() == 0
        assert store.memory_usage() == 0
