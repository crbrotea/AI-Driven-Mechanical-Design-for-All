"""Simple time-window circuit breaker for Vertex AI degraded mode."""
from __future__ import annotations

import time
from threading import Lock


class DegradedModeBreaker:
    """Opens after N consecutive failures, closes after a fixed duration.

    Uses time.monotonic so tests can monkeypatch it deterministically.
    """

    def __init__(self, *, failure_threshold: int, duration_seconds: int) -> None:
        self._threshold = failure_threshold
        self._duration = duration_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = time.monotonic()

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._duration:
                self._opened_at = None
                self._failures = 0
                return False
            return True
