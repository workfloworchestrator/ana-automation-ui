"""Simple in-memory per-key rate limiting."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Fixed-window in-memory rate limiter keyed by an arbitrary string."""

    max_requests: int
    window_seconds: float
    clock: Callable[[], float] = time.monotonic
    _hits: dict[str, list[float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        """Record a hit for the key and report whether it stays within the limit."""
        cutoff = self.clock() - self.window_seconds
        recent = [hit for hit in self._hits.get(key, []) if hit > cutoff]
        allowed = len(recent) < self.max_requests
        if allowed:
            recent.append(self.clock())
        self._hits[key] = recent
        return allowed
