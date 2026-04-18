"""Unit tests for SSE event serialization in Geometry."""
from __future__ import annotations

from services.geometry.api.streaming import GeometrySSEEvent, serialize_geometry_sse


def test_serialize_progress_event() -> None:
    text = serialize_geometry_sse(
        GeometrySSEEvent(
            event="progress",
            data={"step": "building_main", "pct": 10, "primitive": "Flywheel_Rim"},
        )
    )
    assert text.startswith("event: progress\n")
    assert '"step":"building_main"' in text
    assert text.endswith("\n\n")


def test_serialize_final_event() -> None:
    text = serialize_geometry_sse(
        GeometrySSEEvent(
            event="final",
            data={
                "cache_hit": True,
                "intent_hash": "abc123",
                "artifacts": {
                    "step_url": "https://x/s",
                    "glb_url": "https://x/g",
                    "svg_url": "https://x/v",
                },
            },
        )
    )
    assert "event: final" in text
    assert '"cache_hit":true' in text


def test_serialize_error_event() -> None:
    text = serialize_geometry_sse(
        GeometrySSEEvent(
            event="error",
            data={"code": "boolean_operation_failed", "primitive": "Flywheel_Rim"},
        )
    )
    assert "event: error" in text
