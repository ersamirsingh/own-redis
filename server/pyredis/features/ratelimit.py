"""Token bucket and sliding window rate limiting engine."""

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class TokenBucket:
    """In-memory token bucket state."""
    tokens: float
    last_refill: float
    max_tokens: float
    refill_rate: float  # tokens per second


class RateLimiter:
    """Token Bucket and Sliding Window rate limiter."""

    def __init__(self) -> None:
        self._buckets: Dict[str, TokenBucket] = {}

    def check_token_bucket(
        self,
        key: str,
        max_tokens: float,
        refill_rate_per_sec: float,
        requested: float = 1.0,
    ) -> Tuple[bool, float, float]:
        """
        Check and consume tokens from token bucket.
        Returns: (allowed: bool, remaining_tokens: float, retry_after_ms: float)
        """
        now = time.time()
        bucket = self._buckets.get(key)

        if not bucket:
            bucket = TokenBucket(
                tokens=max_tokens,
                last_refill=now,
                max_tokens=max_tokens,
                refill_rate=refill_rate_per_sec,
            )
            self._buckets[key] = bucket

        # Refill tokens based on elapsed time
        elapsed = now - bucket.last_refill
        bucket.last_refill = now
        bucket.tokens = min(bucket.max_tokens, bucket.tokens + (elapsed * bucket.refill_rate))

        if bucket.tokens >= requested:
            bucket.tokens -= requested
            time_to_next_ms = 0.0
            return True, round(bucket.tokens, 2), time_to_next_ms
        else:
            needed = requested - bucket.tokens
            time_to_next_ms = (needed / bucket.refill_rate) * 1000.0 if bucket.refill_rate > 0 else 0.0
            return False, 0.0, round(time_to_next_ms, 1)

    def reset(self, key: str) -> bool:
        """Reset rate limiter state for a key."""
        if key in self._buckets:
            del self._buckets[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all rate limit buckets (for testing)."""
        self._buckets.clear()


# Global RateLimiter singleton
rate_limiter = RateLimiter()
