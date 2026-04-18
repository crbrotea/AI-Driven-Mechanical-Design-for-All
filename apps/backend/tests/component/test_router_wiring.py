"""Component tests for router integration fixes:
- I1: InterpreterMetrics wired and recording data
- C3: DegradedModeBreaker respects settings passed to create_app
- C5: previous_messages flow from session history into orchestrator/Gemma
- I5: Catch-all in SSE stream emits error event for unexpected exceptions
- GET /metrics endpoint returns snapshot
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
)
from services.interpreter.app import create_app
from services.interpreter.domain.errors import ErrorCode, InterpreterError, InterpreterException
from services.interpreter.session.fake_store import FakeSessionStore

BACKEND_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _SuccessGemma(GemmaProtocol):
    """Always returns a valid Shaft intent. Records previous_messages received."""

    def __init__(self) -> None:
        self.received_previous_messages: list[list[dict] | None] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        self.received_previous_messages.append(previous_messages)
        yield GemmaEvent(
            kind="final_json",
            final_json={
                "type": "Shaft",
                "fields": {
                    "diameter_m": {"value": 0.05, "source": "extracted"},
                    "length_m": {"value": 0.5, "source": "extracted"},
                },
                "composed_of": [],
            },
        )


class _ErrorGemma(GemmaProtocol):
    """Always raises VERTEX_AI_TIMEOUT."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        raise InterpreterException(
            InterpreterError(
                code=ErrorCode.VERTEX_AI_TIMEOUT,
                message="timed out",
            )
        )
        yield  # make it a generator


class _BombGemma(GemmaProtocol):
    """Raises an unexpected (non-InterpreterException) error."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        raise RuntimeError("unexpected kaboom")
        yield  # make it a generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def success_gemma() -> _SuccessGemma:
    return _SuccessGemma()


@pytest.fixture
def success_client(success_gemma: _SuccessGemma) -> TestClient:
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=success_gemma,
        session_store=FakeSessionStore(),
    )
    return TestClient(app)


def _stream_body(client: TestClient, prompt: str, session_id: str | None = None) -> str:
    payload: dict[str, Any] = {"prompt": prompt}
    if session_id:
        payload["session_id"] = session_id
    with client.stream("POST", "/interpret", json=payload) as resp:
        return b"".join(resp.iter_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# I1 — Metrics wired and recording
# ---------------------------------------------------------------------------


def test_metrics_recorded_on_success(success_client: TestClient) -> None:
    _stream_body(success_client, "a 5cm shaft")
    resp = success_client.get("/metrics")
    assert resp.status_code == 200
    snapshot = resp.json()
    # request_count for "success" must have at least one entry
    counts = snapshot.get("interpret.request_count", {})
    assert any("success" in key for key in counts)


def test_metrics_endpoint_returns_json(success_client: TestClient) -> None:
    resp = success_client.get("/metrics")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_metrics_records_latency(success_client: TestClient) -> None:
    _stream_body(success_client, "a shaft")
    resp = success_client.get("/metrics")
    snapshot = resp.json()
    latency = snapshot.get("interpret.latency_ms", {})
    assert latency, "Expected latency histogram to have at least one entry"
    # All histogram entries should have count >= 1
    for entry in latency.values():
        assert entry["count"] >= 1


def test_metrics_records_error_on_vertex_failure() -> None:
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_ErrorGemma(),
        session_store=FakeSessionStore(),
    )
    client = TestClient(app)
    _stream_body(client, "a shaft")
    resp = client.get("/metrics")
    snapshot = resp.json()
    counts = snapshot.get("interpret.request_count", {})
    assert any("error" in key for key in counts)


# ---------------------------------------------------------------------------
# C3 — DegradedModeBreaker respects create_app config
# ---------------------------------------------------------------------------


def test_breaker_trips_after_configured_threshold() -> None:
    """With threshold=1 the breaker opens after a single failure."""
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_ErrorGemma(),
        session_store=FakeSessionStore(),
        degraded_mode_failure_threshold=1,
        degraded_mode_duration_seconds=300,
    )
    client = TestClient(app)

    # First request — fails and opens the breaker
    body1 = _stream_body(client, "a shaft")
    assert "error" in body1

    # Second request — breaker is open; degraded-mode response returned immediately
    body2 = _stream_body(client, "another shaft")
    assert "vertex_ai_rate_limit" in body2


def test_breaker_does_not_trip_with_high_threshold() -> None:
    """With threshold=100 a single failure must NOT open the breaker."""
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_ErrorGemma(),
        session_store=FakeSessionStore(),
        degraded_mode_failure_threshold=100,
        degraded_mode_duration_seconds=300,
    )
    client = TestClient(app)
    # First request fails but breaker should stay closed (threshold not reached)
    body1 = _stream_body(client, "a shaft")
    assert "vertex_ai_rate_limit" not in body1

    # Second request also fails normally (not short-circuited by breaker)
    body2 = _stream_body(client, "another shaft")
    assert "vertex_ai_rate_limit" not in body2


# ---------------------------------------------------------------------------
# C5 — previous_messages wired through session → orchestrator → Gemma
# ---------------------------------------------------------------------------


def test_second_request_passes_previous_messages_to_gemma(
    success_client: TestClient, success_gemma: _SuccessGemma
) -> None:
    """After the first request, the second request must receive the prior turn."""
    # First request — creates session
    body1 = _stream_body(success_client, "a 5cm shaft")
    assert "final" in body1

    # Extract session_id from the SSE body
    import json as _json

    session_id: str | None = None
    for line in body1.splitlines():
        if line.startswith("data:"):
            try:
                payload = _json.loads(line[5:].strip())
                if "session_id" in payload:
                    session_id = payload["session_id"]
                    break
            except _json.JSONDecodeError:
                continue

    assert session_id is not None, "Could not extract session_id from first response"

    # Second request — continue the session
    _stream_body(success_client, "make it longer", session_id=session_id)

    # The second call (index 1) should have previous_messages
    assert len(success_gemma.received_previous_messages) >= 2
    second_call_msgs = success_gemma.received_previous_messages[1]
    assert second_call_msgs is not None
    # Should contain at least the user message from the first turn
    roles = [m["role"] for m in second_call_msgs]
    assert "user" in roles


def test_assistant_message_appended_after_success(
    success_client: TestClient,
) -> None:
    """After a successful run, an assistant message must be in session.messages."""
    # We need access to the store to verify — use a named store instance.
    store = FakeSessionStore()
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_SuccessGemma(),
        session_store=store,
    )
    client = TestClient(app)

    body = _stream_body(client, "a 5cm shaft")
    assert "final" in body

    # Retrieve session_id
    import json as _json

    session_id: str | None = None
    for line in body.splitlines():
        if line.startswith("data:"):
            try:
                payload = _json.loads(line[5:].strip())
                if "session_id" in payload:
                    session_id = payload["session_id"]
                    break
            except _json.JSONDecodeError:
                continue

    assert session_id is not None
    # Load the session from the store and check for assistant message
    import asyncio

    session = asyncio.get_event_loop().run_until_complete(store.load(session_id))
    assistant_messages = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_messages) == 1


# ---------------------------------------------------------------------------
# I5 — Catch-all in SSE stream
# ---------------------------------------------------------------------------


def test_unexpected_exception_emits_error_event() -> None:
    """RuntimeError inside generate must produce an SSE error event, not a 500."""
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_BombGemma(),
        session_store=FakeSessionStore(),
    )
    client = TestClient(app)
    body = _stream_body(client, "a shaft")
    assert "event: error" in body
    assert "internal_error" in body
