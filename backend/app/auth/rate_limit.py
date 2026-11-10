import time
import math
import threading
from typing import Dict, Tuple, Optional
from fastapi import HTTPException, status
from app.config import get_settings


class TokenBucketRateLimiter:
    """Thread-safe per-user token bucket rate limiter."""

    def __init__(self, requests_per_minute: Optional[int] = None):
        self._custom_rpm = requests_per_minute
        # user_id -> (tokens: float, last_updated: float)
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    @property
    def capacity(self) -> float:
        if self._custom_rpm is not None:
            return float(self._custom_rpm)
        return float(get_settings().RATE_LIMIT_PER_MIN)

    @property
    def refill_rate(self) -> float:
        # tokens refilled per second
        return self.capacity / 60.0

    def check(self, user_id: str) -> None:
        """
        Check and consume one token for user_id.
        Raises HTTPException(429) with Retry-After header if limit exceeded.
        """
        now = time.monotonic()
        cap = self.capacity
        rate = self.refill_rate

        with self._lock:
            if user_id not in self._buckets:
                tokens = cap - 1.0
                self._buckets[user_id] = (tokens, now)
                return

            last_tokens, last_time = self._buckets[user_id]
            elapsed = max(0.0, now - last_time)
            refilled_tokens = min(cap, last_tokens + elapsed * rate)

            if refilled_tokens >= 1.0:
                self._buckets[user_id] = (refilled_tokens - 1.0, now)
                return

            # Exceeded rate limit
            deficit = 1.0 - refilled_tokens
            retry_after_seconds = max(1, int(math.ceil(deficit / rate))) if rate > 0 else 60
            # Update timestamp and available tokens without deducting
            self._buckets[user_id] = (refilled_tokens, now)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after_seconds)},
        )

    def reset(self, user_id: Optional[str] = None) -> None:
        """Reset rate limiter state (useful for tests)."""
        with self._lock:
            if user_id:
                self._buckets.pop(user_id, None)
            else:
                self._buckets.clear()


# Global default rate limiter instance
rate_limiter = TokenBucketRateLimiter()
