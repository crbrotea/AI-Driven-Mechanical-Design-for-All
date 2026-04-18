"""Server-Sent Events for the Geometry streaming endpoint."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

GeometrySSEEventName = Literal["progress", "final", "error"]


class GeometrySSEEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: GeometrySSEEventName
    data: dict[str, Any]


def serialize_geometry_sse(event: GeometrySSEEvent) -> str:
    """Serialize an event per the SSE wire format."""
    data_json = json.dumps(event.data, separators=(",", ":"))
    return f"event: {event.event}\ndata: {data_json}\n\n"
