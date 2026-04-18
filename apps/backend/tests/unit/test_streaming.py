"""Unit tests for SSE event serialization."""
from __future__ import annotations

from services.interpreter.api.streaming import (
    SSEEvent,
    serialize_sse,
)


def test_serialize_thinking_event() -> None:
    text = serialize_sse(SSEEvent(event="thinking", data={"message": "hi"}))
    assert text == 'event: thinking\ndata: {"message":"hi"}\n\n'


def test_serialize_tool_call_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="tool_call",
            data={"tool": "list_primitives", "reason": "discover"},
        )
    )
    assert "event: tool_call" in text
    assert '"tool":"list_primitives"' in text


def test_serialize_final_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="final",
            data={
                "session_id": "abc",
                "intent": {"type": "Shaft"},
                "language": "en",
            },
        )
    )
    assert "event: final" in text
    assert '"session_id":"abc"' in text


def test_serialize_error_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="error",
            data={"code": "vertex_ai_timeout", "message": "timeout"},
        )
    )
    assert "event: error" in text
