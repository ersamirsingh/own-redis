"""Memory Eviction policies (LRU, LFU, Adaptive) and HOT/WARM/COLD classification."""

import time
from typing import Dict, List, Optional, Tuple
from pyredis.core.exceptions import OutOfMemoryError
from pyredis.core.types import EvictionPolicy
from pyredis.storage.store import DataStore


class EvictionManager:
    """Manages memory eviction strategies and data temperature classification."""

    def __init__(
        self,
        store: DataStore,
        max_memory: int = 256 * 1024 * 1024,
        policy: EvictionPolicy = EvictionPolicy.NOEVICTION,
    ) -> None:
        self.store: DataStore = store
        self.max_memory: int = max_memory
        self.policy: EvictionPolicy = policy
        self.evictions_total: int = 0
        self.evictions_by_key: Dict[str, int] = {}

        # Adaptive eviction weights
        self.weight_frequency: float = -0.35  # High frequency protects from eviction
        self.weight_recency_age: float = 0.40  # High idle time increases eviction score
        self.weight_ttl_urgency: float = 0.15  # Expiring soon increases eviction score
        self.weight_size: float = 0.10  # Large byte footprint slightly favors eviction

    def set_policy(self, policy: EvictionPolicy) -> None:
        """Update active eviction policy."""
        self.policy = policy

    def set_adaptive_weights(
        self,
        weight_frequency: float,
        weight_recency_age: float,
        weight_ttl_urgency: float,
        weight_size: float,
    ) -> None:
        """Customize weights for the Adaptive Eviction algorithm."""
        self.weight_frequency = weight_frequency
        self.weight_recency_age = weight_recency_age
        self.weight_ttl_urgency = weight_ttl_urgency
        self.weight_size = weight_size

    def classify_temperature(self, key: str) -> str:
        """Classify key as HOT, WARM, or COLD based on recency and access frequency."""
        obj = self.store._data.get(key)
        if obj is None:
            return "UNKNOWN"

        now = time.monotonic()
        idle_seconds = now - obj.last_accessed_at

        if idle_seconds < 60 and obj.access_count >= 5:
            return "HOT"
        elif idle_seconds < 300:
            return "WARM"
        else:
            return "COLD"

    def get_temperature_stats(self) -> Dict[str, int]:
        """Return counts of HOT, WARM, and COLD keys across the data store."""
        stats = {"HOT": 0, "WARM": 0, "COLD": 0}
        for key in list(self.store._data.keys()):
            temp = self.classify_temperature(key)
            if temp in stats:
                stats[temp] += 1
        return stats

    def calculate_adaptive_score(self, key: str) -> float:
        """Calculate weighted eviction score for a key. Higher score = higher eviction priority."""
        obj = self.store._data.get(key)
        if obj is None:
            return -1.0

        now_mono = time.monotonic()
        now_epoch = time.time()

        # 1. Recency: idle seconds
        idle_time = max(0.0, now_mono - obj.last_accessed_at)

        # 2. Frequency: access count (log-normalized)
        freq = float(obj.access_count)

        # 3. TTL Urgency: 1 / remaining seconds if TTL set, else 0.0
        ttl_exp = self.store._ttl.get(key)
        if ttl_exp is not None:
            remaining = max(0.1, ttl_exp - now_epoch)
            ttl_urgency = 1.0 / remaining
        else:
            ttl_urgency = 0.0

        # 4. Size in kilobytes
        size_kb = obj.estimated_bytes / 1024.0

        score = (
            (self.weight_recency_age * idle_time)
            + (self.weight_frequency * freq)
            + (self.weight_ttl_urgency * ttl_urgency)
            + (self.weight_size * size_kb)
        )
        return score

    def pick_eviction_candidate(self, policy: Optional[EvictionPolicy] = None) -> Optional[str]:
        """Select the best candidate key to evict under the specified policy."""
        active_policy = policy or self.policy
        keys = list(self.store._data.keys())
        if not keys:
            return None

        if active_policy == EvictionPolicy.NOEVICTION:
            return None

        if active_policy == EvictionPolicy.ALLKEYS_LRU:
            # Key with smallest last_accessed_at (oldest access)
            return min(keys, key=lambda k: self.store._data[k].last_accessed_at)

        if active_policy == EvictionPolicy.VOLATILE_LRU:
            # Keys with TTL only
            volatile_keys = [k for k in keys if k in self.store._ttl]
            if not volatile_keys:
                return None
            return min(volatile_keys, key=lambda k: self.store._data[k].last_accessed_at)

        if active_policy == EvictionPolicy.ALLKEYS_LFU:
            # Key with lowest access_count
            return min(keys, key=lambda k: self.store._data[k].access_count)

        if active_policy == EvictionPolicy.ADAPTIVE:
            # Key with highest weighted eviction score
            return max(keys, key=self.calculate_adaptive_score)

        return None

    def evict_if_needed(self) -> int:
        """Check if memory exceeds max_memory and evict keys until within limit."""
        if self.max_memory <= 0:
            return 0  # No memory limit configured

        evicted_count = 0
        while self.store.memory_usage() > self.max_memory:
            if self.policy == EvictionPolicy.NOEVICTION:
                raise OutOfMemoryError()

            candidate = self.pick_eviction_candidate()
            if candidate is None:
                # Cannot evict any further keys
                break

            self.store.delete(candidate)
            evicted_count += 1
            self.evictions_total += 1
            self.evictions_by_key[candidate] = self.evictions_by_key.get(candidate, 0) + 1

        return evicted_count
