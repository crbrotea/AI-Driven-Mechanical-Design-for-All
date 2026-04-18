"""Unit tests for the degraded-mode circuit breaker."""
from __future__ import annotations

import time

from services.interpreter.agent.circuit_breaker import DegradedModeBreaker


def test_closed_initially() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    assert b.is_open() is False


def test_opens_after_threshold_failures() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    assert b.is_open() is False
    b.record_failure()
    assert b.is_open() is True


def test_success_resets_failures() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    b.record_success()
    b.record_failure()
    assert b.is_open() is False  # counter reset between failures


def test_closes_automatically_after_duration(monkeypatch) -> None:
    current = [1_000_000.0]

    def fake_monotonic() -> float:
        return current[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    b.record_failure()
    assert b.is_open() is True

    current[0] += 61.0
    assert b.is_open() is False
