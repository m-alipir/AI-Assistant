"""Small single-process security primitives for the documented V1 runtime."""

import asyncio
import hashlib
import time
from collections import defaultdict, deque


class ProcessRateLimiter:
    """Bound requests per opaque caller key without retaining an address or credential."""

    def __init__(
        self, max_requests: int, window_seconds: float = 60.0, max_keys: int = 2_048
    ) -> None:
        if max_requests < 1 or window_seconds <= 0 or max_keys < 1:
            raise ValueError("rate limiter limits must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str = "global") -> bool:
        now = time.monotonic()
        async with self._lock:
            cutoff = now - self._window_seconds
            # A hostile peer can otherwise send one request per synthetic client key and
            # retain an unbounded number of deques for the whole process lifetime.
            for candidate, values in tuple(self._timestamps.items()):
                while values and values[0] <= cutoff:
                    values.popleft()
                if not values:
                    del self._timestamps[candidate]
            if key not in self._timestamps and len(self._timestamps) >= self._max_keys:
                oldest_key = min(
                    self._timestamps,
                    key=lambda candidate: self._timestamps[candidate][-1],
                )
                del self._timestamps[oldest_key]
            timestamps = self._timestamps[key]
            if len(timestamps) >= self._max_requests:
                return False
            timestamps.append(now)
            return True


def opaque_client_key(host: str | None) -> str:
    """Hash coarse client identity so limiter state does not retain network addresses."""
    return hashlib.sha256((host or "unknown").encode("utf-8")).hexdigest()[:24]
