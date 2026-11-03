"""Per-IP limit on new guest learners (#210 security review). In-process sliding window.

Built, not a library: limiting one event per IP is a deque per key; slowapi/limits target
route decorators and would add two dependencies for this. Multi-worker deploys get a limit
per worker (documented in decision 0014).
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

GUEST_WINDOW_SECONDS = 3600
GUEST_MAX_PER_WINDOW = int(os.environ.get("MYROAD_GUEST_MAX_PER_HOUR", "20"))


class GuestLimiter:
    def __init__(self, max_per_window: int = GUEST_MAX_PER_WINDOW, window: int = GUEST_WINDOW_SECONDS,
                 clock=time.monotonic) -> None:
        self.max, self.window, self.clock = max_per_window, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.max:
                return False
            q.append(now)
            if len(self._hits) > 10_000:  # bound memory: drop idle keys
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[k]
            return True
