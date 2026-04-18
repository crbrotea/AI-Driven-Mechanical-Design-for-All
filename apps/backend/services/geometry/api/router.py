"""FastAPI router for the Geometry /generate endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from services.geometry.api.dto import (
    GenerateArtifactUrls,
    GenerateRequest,
    GenerateResponse,
)
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


@router.get("/generate/artifacts/{intent_hash}", response_model=GenerateResponse)
async def get_artifacts(intent_hash: str, request: Request) -> GenerateResponse:
    cache = request.app.state.geometry_cache
    cached = await cache.lookup(intent_hash)
    if cached is None:
        raise HTTPException(status_code=404, detail={
            "error": "artifacts_not_found",
            "intent_hash": intent_hash,
        })
    return GenerateResponse(
        cache_hit=True,
        intent_hash=intent_hash,
        artifacts=GenerateArtifactUrls(
            step_url=cached.step_url,
            glb_url=cached.glb_url,
            svg_url=cached.svg_url,
        ),
        mass_properties=cached.mass_properties,
        material_name="unknown",  # lost from cached — acceptable
        material_density_kg_m3=0.0,
    )
