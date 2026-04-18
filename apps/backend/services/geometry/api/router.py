"""FastAPI router for the Geometry /generate endpoint."""

from __future__ import annotations

import time
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
from services.interpreter.observability.logging import get_logger, hash_prompt

router = APIRouter()
logger = get_logger("geometry.router")


@router.post("/generate")
async def generate(req: GenerateRequest, request: Request) -> StreamingResponse:
    pipeline = request.app.state.geometry_pipeline
    metrics = getattr(request.app.state, "metrics", None)
    breaker = getattr(request.app.state, "geometry_cache_breaker", None)

    logger.info(
        "generate_request_started",
        intent_type=req.intent.type,
        composed_of=req.intent.composed_of,
        material_name=req.material_name,
        intent_hash_preview=hash_prompt(str(req.intent.model_dump()))[:16],
    )

    async def event_stream() -> AsyncIterator[bytes]:
        start = time.monotonic()
        cache_hit = False
        intent_type = req.intent.type
        try:
            if breaker and breaker.is_open():
                yield serialize_geometry_sse(
                    GeometrySSEEvent(
                        event="error",
                        data={
                            "code": "gcs_unavailable",
                            "message": (
                                "Geometry cache temporarily unavailable. "
                                "Please retry."
                            ),
                            "retry_after": 60,
                        },
                    )
                ).encode("utf-8")
                return

            async for ev in pipeline.generate_streaming(
                intent=req.intent,
                material_name=req.material_name,
            ):
                if ev["event"] == "final":
                    cache_hit = bool(ev["data"].get("cache_hit"))
                yield serialize_geometry_sse(
                    GeometrySSEEvent(event=ev["event"], data=ev["data"])
                ).encode("utf-8")
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "generate_request_completed",
                intent_type=intent_type,
                cache_hit=cache_hit,
                latency_ms=elapsed_ms,
            )
            if metrics is not None:
                metrics.request_count_inc(
                    status="success",
                    language="n/a",
                    intent_type=intent_type,
                )
                metrics.latency_ms_record(intent_type=intent_type, value_ms=elapsed_ms)
            if breaker:
                breaker.record_success()
        except GeometryException as e:
            logger.warning(
                "generate_request_failed",
                intent_type=intent_type,
                error_code=e.error.code.value,
                primitive=e.error.primitive,
                stage=e.error.stage,
            )
            if metrics is not None:
                metrics.request_count_inc(
                    status="error", language="n/a", intent_type=intent_type,
                )
                metrics.retry_count_inc(error_code=e.error.code.value)
            if breaker and e.error.code in ("gcs_upload_failed", "gcs_unavailable"):
                breaker.record_failure()
            yield serialize_geometry_sse(
                GeometrySSEEvent(event="error", data=e.error.model_dump(mode="json"))
            ).encode("utf-8")
        except Exception as e:
            logger.exception("generate_unhandled_error", intent_type=intent_type)
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
