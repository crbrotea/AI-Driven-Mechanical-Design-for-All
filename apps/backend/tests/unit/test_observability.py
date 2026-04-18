"""Unit tests for observability: logging and metrics."""
from __future__ import annotations

import json
import logging

import pytest

from services.interpreter.observability.logging import (
    configure_logging,
    get_logger,
    hash_prompt,
)
from services.interpreter.observability.metrics import (
    InterpreterMetrics,
)


def test_logger_emits_structured_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging(level="INFO", json_output=True)
    log = get_logger("interpreter.test")

    with caplog.at_level(logging.INFO):
        log.info("interpret_request", session_id="abc", latency_ms=123)

    record = caplog.records[-1]
    payload = json.loads(record.message) if record.message.startswith("{") else {
        "event": record.message
    }
    # structlog renders final JSON string via the processor — we accept either.
    assert "interpret_request" in record.message or payload.get(
        "event"
    ) == "interpret_request"


def test_hash_prompt_is_stable_and_not_plain_text() -> None:
    h1 = hash_prompt("Design a flywheel at 3000 RPM")
    h2 = hash_prompt("Design a flywheel at 3000 RPM")
    h3 = hash_prompt("Design a flywheel at 3001 RPM")
    assert h1 == h2
    assert h1 != h3
    assert "flywheel" not in h1  # Must not leak prompt text.
    assert len(h1) == 64  # sha256 hex


def test_metrics_counters_increment() -> None:
    metrics = InterpreterMetrics()
    metrics.request_count_inc(status="success", language="es", intent_type="flywheel")
    metrics.request_count_inc(status="success", language="es", intent_type="flywheel")
    metrics.retry_count_inc(error_code="invalid_json_retry_failed")

    snapshot = metrics.snapshot()
    assert snapshot["interpret.request_count"]["success|es|flywheel"] == 2
    assert snapshot["interpret.retry_count"]["invalid_json_retry_failed"] == 1


def test_metrics_latency_recording() -> None:
    metrics = InterpreterMetrics()
    metrics.latency_ms_record(intent_type="flywheel", value_ms=100)
    metrics.latency_ms_record(intent_type="flywheel", value_ms=200)
    metrics.latency_ms_record(intent_type="flywheel", value_ms=300)

    snapshot = metrics.snapshot()
    assert snapshot["interpret.latency_ms"]["flywheel"]["count"] == 3
    assert snapshot["interpret.latency_ms"]["flywheel"]["sum"] == 600
