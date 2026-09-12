"""Metrics collection, latency percentiles, hot-key detection, and slow query logging."""

import math
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SlowLogEntry:
    """Entry stored in the circular slow query log."""
    id: int
    timestamp: float
    duration_ms: float
    command: str
    args: List[str]
    client_peer: str

    def to_resp(self) -> List[Any]:
        """Convert entry into standard RESP slowlog nested array representation."""
        return [
            self.id,
            int(self.timestamp),
            int(self.duration_ms * 1000),  # microseconds in Redis slowlog
            [self.command] + self.args,
            self.client_peer,
            "",
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "args": self.args,
            "client_peer": self.client_peer,
        }


class HotKeyDetector:
    """Sliding-window frequency tracker to identify hot keys causing contention."""

    def __init__(self, window_seconds: float = 60.0, max_keys: int = 2000) -> None:
        self.window_seconds: float = window_seconds
        self.max_keys: int = max_keys
        # (timestamp, key)
        self._access_log: deque = deque()
        self._counts: Counter = Counter()

    def record_access(self, key: str) -> None:
        now = time.time()
        self._access_log.append((now, key))
        self._counts[key] += 1
        self._prune(now)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._access_log and self._access_log[0][0] < cutoff:
            _, old_key = self._access_log.popleft()
            self._counts[old_key] -= 1
            if self._counts[old_key] <= 0:
                del self._counts[old_key]

    def get_top_hot_keys(self, limit: int = 10) -> List[Tuple[str, int]]:
        self._prune(time.time())
        return self._counts.most_common(limit)


class MetricsCollector:
    """Central metrics collector for throughput, latency, cache hit ratios, and slow logs."""

    def __init__(
        self,
        slow_threshold_ms: float = 5.0,
        max_slow_entries: int = 128,
        max_latency_samples: int = 5000,
    ) -> None:
        self.slow_threshold_ms: float = slow_threshold_ms
        self.max_slow_entries: int = max_slow_entries
        self.max_latency_samples: int = max_latency_samples

        self.start_time: float = time.time()
        self.total_commands: int = 0
        self.command_counts: Counter = Counter()
        self.latency_samples: deque = deque(maxlen=max_latency_samples)

        # Cache analytics
        self.cache_hits: int = 0
        self.cache_misses: int = 0

        # Slow log
        self._slow_log: deque = deque(maxlen=max_slow_entries)
        self._slow_id_counter: int = 0

        # Hot keys
        self.hot_keys: HotKeyDetector = HotKeyDetector()

    def record_command(
        self,
        command: str,
        duration_ms: float,
        key: Optional[str] = None,
        args: Optional[List[str]] = None,
        client_peer: str = "127.0.0.1:0",
    ) -> None:
        """Record command completion, latency sample, and check slow threshold."""
        cmd_upper = command.upper()
        self.total_commands += 1
        self.command_counts[cmd_upper] += 1
        self.latency_samples.append(duration_ms)

        if key:
            self.hot_keys.record_access(key)

        # Check slow log threshold
        if duration_ms >= self.slow_threshold_ms:
            self._slow_id_counter += 1
            entry = SlowLogEntry(
                id=self._slow_id_counter,
                timestamp=time.time(),
                duration_ms=round(duration_ms, 3),
                command=cmd_upper,
                args=args or [],
                client_peer=client_peer,
            )
            self._slow_log.append(entry)

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def get_hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 100.0
        return round((self.cache_hits / total) * 100.0, 2)

    def get_latency_percentiles(self) -> Dict[str, float]:
        """Compute P50, P90, P95, P99 latency percentiles over recent samples."""
        if not self.latency_samples:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0}

        sorted_samples = sorted(self.latency_samples)
        n = len(sorted_samples)

        def percentile(p: float) -> float:
            k = (n - 1) * p
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return sorted_samples[int(k)]
            d0 = sorted_samples[int(f)] * (c - k)
            d1 = sorted_samples[int(c)] * (k - f)
            return d0 + d1

        return {
            "p50": round(percentile(0.50), 3),
            "p90": round(percentile(0.90), 3),
            "p95": round(percentile(0.95), 3),
            "p99": round(percentile(0.99), 3),
            "avg": round(sum(sorted_samples) / n, 3),
        }

    def get_ops_per_sec(self) -> float:
        uptime = max(0.1, time.time() - self.start_time)
        return round(self.total_commands / uptime, 2)

    def get_slow_log(self, limit: int = 10) -> List[SlowLogEntry]:
        return list(reversed(list(self._slow_log)))[:limit]

    def slow_log_len(self) -> int:
        return len(self._slow_log)

    def slow_log_reset(self) -> None:
        self._slow_log.clear()

    def get_summary(self) -> Dict[str, Any]:
        """Telemetry snapshot consumed by REST API, WebSockets, and Gemini diagnostics."""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": round(uptime, 1),
            "total_commands": self.total_commands,
            "ops_per_sec": self.get_ops_per_sec(),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_ratio_percent": self.get_hit_ratio(),
            "latency": self.get_latency_percentiles(),
            "top_commands": dict(self.command_counts.most_common(10)),
            "hot_keys": [{"key": k, "hits": c} for k, c in self.hot_keys.get_top_hot_keys(5)],
            "slow_queries_count": len(self._slow_log),
        }


# Global collector singleton
metrics_collector = MetricsCollector()
