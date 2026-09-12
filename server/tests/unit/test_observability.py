"""Unit tests for EventBus, Distributed Tracing, Metrics, and SLOWLOG."""

import time
import pytest
from pyredis.commands import CommandContext, registry
from pyredis.core.types import Role
from pyredis.events import Event, EventBus, EventType
from pyredis.metrics import HotKeyDetector, MetricsCollector
from pyredis.protocol.types import SimpleString
from pyredis.storage import DataStore
from pyredis.tracing import Tracer, sanitize_arguments


class TestEventBus:
    def test_publish_and_subscribe(self) -> None:
        bus = EventBus()
        received = []

        def on_key_updated(ev: Event) -> None:
            received.append(ev)

        bus.subscribe(EventType.KEY_UPDATED, on_key_updated)
        bus.publish(Event(type=EventType.KEY_UPDATED, key="user:1"))
        # Should not trigger for deleted
        bus.publish(Event(type=EventType.KEY_DELETED, key="user:2"))

        assert len(received) == 1
        assert received[0].key == "user:1"

    def test_wildcard_subscriber(self) -> None:
        bus = EventBus()
        all_events = []

        bus.subscribe("*", lambda ev: all_events.append(ev))
        bus.publish(Event(type=EventType.KEY_CREATED, key="k1"))
        bus.publish(Event(type=EventType.SLOW_COMMAND, metadata={"ms": 12.0}))

        assert len(all_events) == 2

    def test_recent_events_filter(self) -> None:
        bus = EventBus()
        bus.publish(Event(type=EventType.KEY_CREATED, key="a"))
        bus.publish(Event(type=EventType.KEY_UPDATED, key="b"))
        bus.publish(Event(type=EventType.KEY_CREATED, key="c"))

        created = bus.get_recent_events(event_type=EventType.KEY_CREATED)
        assert len(created) == 2
        assert created[0]["key"] == "c"


class TestDistributedTracing:
    def test_trace_and_spans(self) -> None:
        tracer = Tracer(max_traces=50)
        trace = tracer.start_trace("SET", ["session", "xyz"], client_id="c1", client_ip="127.0.0.1:5000")

        with tracer.span(trace, "storage", metadata={"tier": "RAM"}):
            time.sleep(0.005)

        with tracer.span(trace, "aof"):
            time.sleep(0.002)

        trace.finish(status="OK")
        tracer.record_trace(trace)

        retrieved = tracer.get_trace(trace.trace_id)
        assert retrieved is not None
        assert retrieved["command"] == "SET"
        assert retrieved["duration_ms"] >= 6.0
        assert len(retrieved["spans"]) == 2
        assert retrieved["spans"][0]["name"] == "storage"
        assert retrieved["spans"][0]["metadata"]["tier"] == "RAM"

    def test_argument_masking(self) -> None:
        # Sensitive commands must mask parameters
        sanitized = sanitize_arguments("AUTH", ["default", "mySuperSecretPassword123"])
        assert sanitized == ["default", "******"]

        # Long parameters should truncate cleanly
        long_val = "x" * 200
        sanitized_long = sanitize_arguments("SET", ["k", long_val])
        assert sanitized_long[1].endswith("...")
        assert len(sanitized_long[1]) == 100


class TestMetricsCollector:
    def test_command_counters_and_percentiles(self) -> None:
        collector = MetricsCollector(max_latency_samples=100)
        # Record 100 samples with latencies 1ms to 100ms
        for i in range(1, 101):
            collector.record_command("GET", float(i))

        percentiles = collector.get_latency_percentiles()
        assert 49.0 <= percentiles["p50"] <= 51.0
        assert 89.0 <= percentiles["p90"] <= 91.0
        assert 94.0 <= percentiles["p95"] <= 96.0
        assert 98.0 <= percentiles["p99"] <= 100.0

    def test_cache_hit_ratio(self) -> None:
        collector = MetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        # 3 hits, 1 miss = 75%
        assert collector.get_hit_ratio() == 75.0

    def test_hot_key_detection(self) -> None:
        detector = HotKeyDetector(window_seconds=60.0)
        for _ in range(25):
            detector.record_access("leaderboard")
        for _ in range(5):
            detector.record_access("profile:user")

        top = detector.get_top_hot_keys(2)
        assert top[0] == ("leaderboard", 25)
        assert top[1] == ("profile:user", 5)

    def test_slow_query_log(self) -> None:
        collector = MetricsCollector(slow_threshold_ms=5.0)
        # Fast query
        collector.record_command("GET", 1.2)
        assert collector.slow_log_len() == 0

        # Slow query
        collector.record_command("KEYS", 15.5, key=None, args=["*"], client_peer="127.0.0.1:6000")
        assert collector.slow_log_len() == 1

        entries = collector.get_slow_log()
        assert entries[0].command == "KEYS"
        assert entries[0].duration_ms == 15.5

        # Test SLOWLOG commands
        store = DataStore()
        ctx = CommandContext(store=store, role=Role.ADMIN, metrics=collector)

        # SLOWLOG LEN
        assert registry.execute("SLOWLOG", ["LEN"], ctx) == 1

        # SLOWLOG GET
        res = registry.execute("SLOWLOG", ["GET"], ctx)
        assert len(res) == 1
        assert res[0][3] == ["KEYS", "*"]

        # SLOWLOG RESET
        assert registry.execute("SLOWLOG", ["RESET"], ctx) == SimpleString("OK")
        assert registry.execute("SLOWLOG", ["LEN"], ctx) == 0
