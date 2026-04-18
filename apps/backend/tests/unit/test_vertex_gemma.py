"""Unit tests for VertexGemmaClient — error mapping, timeout, and streaming."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exc

from services.interpreter.agent.vertex_gemma import VertexGemmaClient
from services.interpreter.domain.errors import ErrorCode, InterpreterException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_text_chunk(text: str) -> MagicMock:
    """Build a fake Vertex streaming chunk containing a text part."""
    part = MagicMock()
    part.text = text
    part.function_call = None

    candidate = MagicMock()
    candidate.content.parts = [part]

    chunk = MagicMock()
    chunk.candidates = [candidate]
    return chunk


def _make_tool_call_chunk(name: str, args: dict[str, Any]) -> MagicMock:
    """Build a fake Vertex streaming chunk containing a function_call part."""
    fc = MagicMock()
    fc.name = name
    fc.args = args

    part = MagicMock()
    part.function_call = fc
    part.text = None

    candidate = MagicMock()
    candidate.content.parts = [part]

    chunk = MagicMock()
    chunk.candidates = [candidate]
    return chunk


async def _async_gen(*chunks: MagicMock) -> AsyncIterator[MagicMock]:
    """Yield chunks as an async generator (simulates stream=True response)."""
    for chunk in chunks:
        yield chunk


async def _collect(client: VertexGemmaClient, **kwargs: Any) -> list:
    events = []
    async for ev in client.generate(**kwargs):
        events.append(ev)
    return events


TOOLS: list[dict[str, Any]] = []
BASE_KWARGS = dict(system_prompt="sys", user_prompt="user", tools=TOOLS)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> VertexGemmaClient:
    with (
        patch("services.interpreter.agent.vertex_gemma.aiplatform.init"),
        patch("services.interpreter.agent.vertex_gemma.GenerativeModel"),
    ):
        c = VertexGemmaClient(
            project_id="test-project",
            region="us-central1",
            model_name="gemma-4",
            timeout_seconds=2,
        )
    return c


# ---------------------------------------------------------------------------
# C2 — exception → ErrorCode mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asyncio_timeout_maps_to_vertex_ai_timeout(client: VertexGemmaClient) -> None:
    """asyncio.TimeoutError should surface as VERTEX_AI_TIMEOUT."""

    async def _raise_timeout(*args: Any, **kwargs: Any) -> None:
        raise TimeoutError

    client._model.generate_content_async = _raise_timeout  # type: ignore[assignment]

    with pytest.raises(InterpreterException) as exc_info:
        await _collect(client, **BASE_KWARGS)

    assert exc_info.value.error.code == ErrorCode.VERTEX_AI_TIMEOUT


@pytest.mark.asyncio
async def test_deadline_exceeded_maps_to_vertex_ai_timeout(client: VertexGemmaClient) -> None:
    """google DeadlineExceeded should map to VERTEX_AI_TIMEOUT."""

    async def _raise(*args: Any, **kwargs: Any) -> None:
        raise google_exc.DeadlineExceeded("deadline")

    client._model.generate_content_async = _raise  # type: ignore[assignment]

    with pytest.raises(InterpreterException) as exc_info:
        await _collect(client, **BASE_KWARGS)

    assert exc_info.value.error.code == ErrorCode.VERTEX_AI_TIMEOUT


@pytest.mark.asyncio
async def test_resource_exhausted_maps_to_rate_limit(client: VertexGemmaClient) -> None:
    """ResourceExhausted should map to VERTEX_AI_RATE_LIMIT."""

    async def _raise(*args: Any, **kwargs: Any) -> None:
        raise google_exc.ResourceExhausted("quota")

    client._model.generate_content_async = _raise  # type: ignore[assignment]

    with pytest.raises(InterpreterException) as exc_info:
        await _collect(client, **BASE_KWARGS)

    assert exc_info.value.error.code == ErrorCode.VERTEX_AI_RATE_LIMIT


@pytest.mark.asyncio
async def test_service_unavailable_maps_to_vertex_ai_timeout(client: VertexGemmaClient) -> None:
    """ServiceUnavailable should map to VERTEX_AI_TIMEOUT."""

    async def _raise(*args: Any, **kwargs: Any) -> None:
        raise google_exc.ServiceUnavailable("down")

    client._model.generate_content_async = _raise  # type: ignore[assignment]

    with pytest.raises(InterpreterException) as exc_info:
        await _collect(client, **BASE_KWARGS)

    assert exc_info.value.error.code == ErrorCode.VERTEX_AI_TIMEOUT


# ---------------------------------------------------------------------------
# C6 — real streaming
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_tool_call_emitted_immediately(client: VertexGemmaClient) -> None:
    """A function_call chunk must produce a tool_call GemmaEvent."""
    tool_chunk = _make_tool_call_chunk("cut_scene", {"at": 5.0})

    async def _stream(*args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
        return _async_gen(tool_chunk)

    client._model.generate_content_async = _stream  # type: ignore[assignment]

    events = await _collect(client, **BASE_KWARGS)

    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "tool_call"
    assert ev.tool_call is not None
    assert ev.tool_call.name == "cut_scene"
    assert ev.tool_call.args == {"at": 5.0}


@pytest.mark.asyncio
async def test_streaming_final_json_emitted_from_text_chunk(client: VertexGemmaClient) -> None:
    """A text chunk containing JSON must produce a final_json GemmaEvent."""
    payload = {"summary": "intro scene"}
    text_chunk = _make_text_chunk(json.dumps(payload))

    async def _stream(*args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
        return _async_gen(text_chunk)

    client._model.generate_content_async = _stream  # type: ignore[assignment]

    events = await _collect(client, **BASE_KWARGS)

    assert len(events) == 1
    assert events[0].kind == "final_json"
    assert events[0].final_json == payload


# ---------------------------------------------------------------------------
# C5 wiring — previous_messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_previous_messages_included_in_request(client: VertexGemmaClient) -> None:
    """previous_messages must be wired into the Vertex content list."""
    captured: list[Any] = []

    async def _stream(contents: Any, *args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
        captured.extend(contents if isinstance(contents, list) else [contents])
        return _async_gen()  # empty stream — we only care about the call args

    client._model.generate_content_async = _stream  # type: ignore[assignment]

    previous = [
        {"role": "user", "content": "hello"},
        {"role": "model", "content": "hi there"},
    ]

    await _collect(
        client,
        system_prompt="sys",
        user_prompt="next question",
        tools=TOOLS,
        previous_messages=previous,
    )

    # At minimum 4 items: system + 2 previous + new user
    assert len(captured) >= 4
