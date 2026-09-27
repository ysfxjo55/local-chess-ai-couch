from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(bucket: str, limit: int, window_seconds: int) -> Callable:
    """Small dependency for a single-process SQLite deployment.

    It deliberately keys by route and client IP. The durable database remains
    the authority for data; this guard prevents accidental or trivial abusive
    bursts until a multi-process edge limiter is deployed.
    """

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client}"
        now = time.monotonic()
        with _lock:
            entries = _windows[key]
            while entries and entries[0] <= now - window_seconds:
                entries.popleft()
            if len(entries) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")
            entries.append(now)

    return dependency
