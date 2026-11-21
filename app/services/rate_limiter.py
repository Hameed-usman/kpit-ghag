"""
Ghag – In-Memory Client IP Rate Limiter (FR-16).

Zero-dependency, thread-safe, sliding window rate limiter.
Enforces default 10 requests per minute per client IP.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, List, Tuple


class InMemoryRateLimiter:
    """Sliding-window rate limiter per client IP."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, client_ip: str, limit: int) -> Tuple[bool, int]:
        """
        Check if client_ip is within limit requests per window_seconds.
        Returns (allowed: bool, retry_after_seconds: int).
        """
        if limit <= 0:
            return True, 0

        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._history[client_ip]
            # Prune expired timestamps
            valid = [ts for ts in timestamps if ts > cutoff]
            self._history[client_ip] = valid

            if len(valid) >= limit:
                oldest = valid[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, retry_after

            valid.append(now)
            return True, 0

    def reset(self) -> None:
        """Reset history (for tests)."""
        with self._lock:
            self._history.clear()


rate_limiter = InMemoryRateLimiter(window_seconds=60)

RATE_LIMIT_DETAIL = (
    "Too many requests. Please wait a minute before asking again. / "
    "ډېرې غوښتنې وشوې، مهرباني وکړئ لږ انتظار وکړئ. / "
    "بہت زیادہ درخواستیں، برائے مہربانی ایک منٹ انتظار کریں۔"
)
