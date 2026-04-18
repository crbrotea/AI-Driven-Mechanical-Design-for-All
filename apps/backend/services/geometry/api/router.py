"""FastAPI router for the Geometry /generate endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from services.geometry.api.dto import GenerateRequest
from services.geometry.api.streaming import (
    GeometrySSEEvent,
    serialize_geometry_sse,
)
from services.geometry.domain.errors import GeometryException

router = APIRouter()


@router.post("/generate")
async def generate(req: GenerateRequest, request: Request) -> StreamingResponse:
    pipeline = request.app.state.geometry_pipeline

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for ev in pipeline.generate_streaming(
                intent=req.intent,
                material_name=req.material_name,
            ):
                yield serialize_geometry_sse(
                    GeometrySSEEvent(event=ev["event"], data=ev["data"])
                ).encode("utf-8")
        except GeometryException as e:
            yield serialize_geometry_sse(
                GeometrySSEEvent(event="error", data=e.error.model_dump(mode="json"))
            ).encode("utf-8")
        except Exception as e:
            yield serialize_geometry_sse(
                GeometrySSEEvent(
                    event="error",
                    data={
                        "code": "internal_error",
                        "message": f"Unexpected error: {e}",
                    },
                )
            ).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
