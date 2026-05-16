"""POST /explain router with SSE event stream."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse

from services.explainer.domain.errors import ExplainException
from services.explainer.domain.models import ExplainRequest
from services.explainer.generator import Explainer, ExplainEvent
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult

_logger = structlog.get_logger("explainer.router")

router = APIRouter(tags=["explainer"])


def _serialize(event: ExplainEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, separators=(',', ':'))}\n\n"


async def _stream(
    explainer: Explainer,
    intent: DesignIntent,
    analysis_result: AnalysisResult,
) -> AsyncIterator[str]:
    try:
        async for event in explainer.explain_streaming(intent, analysis_result):
            yield _serialize(event)
    except ExplainException as exc:
        _logger.warning(
            "explain_failed",
            code=exc.error.code.value,
            intent_type=intent.type,
        )
        err = ExplainEvent(event="error", data=exc.error.model_dump())
        yield _serialize(err)


@router.post("/explain")
async def explain(req: ExplainRequest, app_req: Request) -> StreamingResponse:
    explainer: Explainer = app_req.app.state.explainer
    _logger.info(
        "explain_request_started",
        intent_type=req.intent.type,
        verdict=req.analysis_result.verdict.value,
        session_id=req.session_id,
    )
    return StreamingResponse(
        _stream(explainer, req.intent, req.analysis_result),
        media_type="text/event-stream",
    )


def register_explainer_router(app: FastAPI) -> None:
    """Attach the explainer router. Caller wires app.state.explainer."""
    app.include_router(router)
