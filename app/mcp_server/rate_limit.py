"""Per-client rate limits for MCP tools.

Two fixed policies: tools that only read the database, and tools that call a
model provider. Each policy has a per-minute token bucket and, for model
calls, a rolling daily cap. State is in process memory, so limits reset on
restart and apply per server instance.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

Clock = Callable[[], float]


@dataclass(frozen=True)
class LimitPolicy:
    per_minute: int
    per_day: int | None = None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_seconds: int = 0


class _Bucket:
    def __init__(self, capacity: int, now: float) -> None:
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated = now

    def take(self, now: float) -> float:
        """Return 0 if a token was taken, else seconds until one is available."""
        rate = self.capacity / 60.0
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * rate)
        self.updated = now
        if self.tokens >= 1:
            self.tokens -= 1
            return 0.0
        return (1 - self.tokens) / rate


class RateLimiter:
    DAY_SECONDS = 86_400

    def __init__(self, policies: dict[str, LimitPolicy], clock: Clock = time.monotonic) -> None:
        self._policies = policies
        self._clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._daily: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client_id: str, policy_name: str) -> Decision:
        policy = self._policies[policy_name]
        key = (client_id, policy_name)
        with self._lock:
            now = self._clock()
            if policy.per_day is not None:
                window = self._daily.setdefault(key, deque())
                while window and now - window[0] >= self.DAY_SECONDS:
                    window.popleft()
                if len(window) >= policy.per_day:
                    return Decision(False, max(1, math.ceil(self.DAY_SECONDS - (now - window[0]))))
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = _Bucket(policy.per_minute, now)
            wait = bucket.take(now)
            if wait > 0:
                return Decision(False, max(1, math.ceil(wait)))
            if policy.per_day is not None:
                self._daily[key].append(now)
            return Decision(True)
