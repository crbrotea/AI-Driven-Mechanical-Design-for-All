"""Server-Sent Events serialization for the Interpreter streaming endpoint."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SSEEventName = Literal[
    "thinking", "tool_call", "tool_result", "partial_intent", "final", "error"
]


class SSEEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: SSEEventName
    data: dict[str, Any]


def serialize_sse(event: SSEEvent) -> str:
    """Serialize an event per the SSE wire format.

    Output: "event: <name>\\ndata: <json>\\n\\n"
    """
    data_json = json.dumps(event.data, separators=(",", ":"))
    return f"event: {event.event}\ndata: {data_json}\n\n"
