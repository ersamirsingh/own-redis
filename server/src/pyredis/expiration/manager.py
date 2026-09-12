"""TTL and Active Expiration Engine using Min-Heap."""

import asyncio
import heapq
import logging
import time
from typing import Dict, List, Optional, Tuple
from pyredis.storage.store import DataStore

logger = logging.getLogger("pyredis.expiration")


class ExpirationManager:
    """Manages key expiration with a min-heap for O(1) earliest-expiration peek

    and background active sweeping.
    """

    def __init__(self, store: DataStore) -> None:
        self.store: DataStore = store
        # Heap contains tuples: (expiry_epoch_sec, key)
        self._heap: List[Tuple[float, str]] = []
        self._worker_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._expired_total: int = 0

    @property
    def expired_total(self) -> int:
        return self._expired_total

    def set_expiration(self, key: str, expire_at: float) -> bool:
        """Set key expiration and schedule in min-heap."""
        if not self.store.exists(key):
            return False
        self.store.set_ttl(key, expire_at)
        heapq.heappush(self._heap, (expire_at, key))
        return True

    def persist(self, key: str) -> bool:
        """Remove expiration from key."""
        return self.store.persist(key)

    def start_worker(self) -> None:
        """Start background active expiration worker task."""
        if self._worker_task is None or self._worker_task.done():
            self._running = True
            self._worker_task = asyncio.create_task(self._active_sweep_loop())
            logger.info("Active expiration background worker started")

    async def stop_worker(self) -> None:
        """Stop background active expiration worker task."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Active expiration background worker stopped")

    def sweep_now(self) -> int:
        """Synchronously sweep and remove all expired keys up to current time."""
        now = time.time()
        removed = 0

        while self._heap:
            exp_time, key = self._heap[0]
            if exp_time > now:
                break

            heapq.heappop(self._heap)

            # Validate that key still exists and hasn't had its TTL altered
            current_ttl_exp = self.store._ttl.get(key)
            if current_ttl_exp is not None:
                # Floating point equality check with small epsilon
                if abs(current_ttl_exp - exp_time) < 0.001:
                    if self.store.delete(key):
                        removed += 1
                        self._expired_total += 1

        return removed

    async def _active_sweep_loop(self) -> None:
        """Active background loop checking min-heap."""
        while self._running:
            try:
                now = time.time()
                self.sweep_now()

                # Determine how long to sleep
                if self._heap:
                    next_exp = self._heap[0][0]
                    sleep_time = max(0.01, min(next_exp - now, 0.1))
                else:
                    sleep_time = 0.1

                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in active sweep loop: {e}")
                await asyncio.sleep(0.5)

    def get_metrics(self) -> Dict[str, object]:
        """Compute detailed TTL distribution metrics for dashboards."""
        now = time.time()
        total_keys = self.store.dbsize()
        with_ttl = len(self.store._ttl)
        without_ttl = max(0, total_keys - with_ttl)

        ttl_values = [max(0.0, exp - now) for exp in self.store._ttl.values()]
        avg_ttl = (sum(ttl_values) / len(ttl_values)) if ttl_values else 0.0

        # Distribution buckets
        buckets = {
            "under_10s": 0,
            "10s_to_1m": 0,
            "1m_to_1h": 0,
            "over_1h": 0,
        }
        for ttl in ttl_values:
            if ttl < 10:
                buckets["under_10s"] += 1
            elif ttl < 60:
                buckets["10s_to_1m"] += 1
            elif ttl < 3600:
                buckets["1m_to_1h"] += 1
            else:
                buckets["over_1h"] += 1

        return {
            "total_keys": total_keys,
            "keys_with_ttl": with_ttl,
            "keys_without_ttl": without_ttl,
            "avg_ttl_seconds": round(avg_ttl, 2),
            "expired_total": self._expired_total,
            "distribution": buckets,
        }
