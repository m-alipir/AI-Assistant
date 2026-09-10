"""Small single-process security primitives for the documented V1 runtime."""

import asyncio
import hashlib
import time
from collections import defaultdict, deque


class ProcessRateLimiter:
    """Bound requests per opaque caller key without retaining an address or credential."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str = "global") -> bool:
        now = time.monotonic()
        async with self._lock:
            cutoff = now - self._window_seconds
            timestamps = self._timestamps[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self._max_requests:
                return False
            timestamps.append(now)
            if len(self._timestamps) > 2_048:
                self._timestamps = defaultdict(
                    deque, {value: times for value, times in self._timestamps.items() if times}
                )
            return True


def opaque_client_key(host: str | None) -> str:
    """Hash coarse client identity so limiter state does not retain network addresses."""
    return hashlib.sha256((host or "unknown").encode("utf-8")).hexdigest()[:24]
