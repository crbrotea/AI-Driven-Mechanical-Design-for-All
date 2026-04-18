"""FastAPI router for the Interpreter endpoints."""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.api.dto import (
    InterpretRequest,
    InterpretResponse,
    RefineRequest,
)
from services.interpreter.api.streaming import SSEEvent, serialize_sse
from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
    InterpreterException,
)
from services.interpreter.domain.intent import FieldSource
from services.interpreter.domain.validators import validate_physical_consistency
from services.interpreter.observability.logging import get_logger, hash_prompt
from services.interpreter.session.merge import merge_refinement
from services.interpreter.session.store import Session, SessionMessage

router = APIRouter()


def _detect_language(text: str) -> Literal["es", "en"]:
    # Minimal heuristic; replaced by Gemma-reported language post-generation.
    es_markers = {"diseña", "necesito", "un ", "una ", "con ", "para "}
    lower = text.lower()
    return "es" if any(m in lower for m in es_markers) else "en"


@router.get("/metrics")
async def get_metrics(request: Request) -> dict[str, Any]:
    """Return a snapshot of in-process metrics (debug endpoint)."""
    from services.interpreter.observability.metrics import InterpreterMetrics

    metrics: InterpreterMetrics = request.app.state.metrics
    return metrics.snapshot()


@router.post("/interpret")
async def interpret(req: InterpretRequest, request: Request) -> StreamingResponse:
    orchestrator: Orchestrator = request.app.state.orchestrator
    store = request.app.state.session_store
    registry = request.app.state.registry
    metrics = request.app.state.metrics

    language = _detect_language(req.prompt)
    logger = get_logger("interpreter.router")

    async def event_stream() -> AsyncIterator[bytes]:
        # Degraded mode check
        breaker = request.app.state.breaker
        if breaker.is_open():
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data={
                        "code": ErrorCode.VERTEX_AI_RATE_LIMIT,
                        "message": (
                            "AI assistant temporarily unavailable. "
                            "Please use manual mode or retry in 60 seconds."
                        ),
                        "retry_after": 60,
                    },
                )
            ).encode("utf-8")
            return

        session: Session | None = None
        try:
            if req.session_id:
                session = await store.load(req.session_id)
            else:
                session = await store.create_session(
                    user_id="anonymous", language=language
                )

            await store.append_message(
                session.session_id,
                SessionMessage(
                    role="user", content=req.prompt, timestamp=datetime.now(UTC)
                ),
            )

            logger.info(
                "interpret_request_started",
                session_id=session.session_id,
                prompt_length=len(req.prompt),
                prompt_hash=hash_prompt(req.prompt),
                language=language,
            )

            yield serialize_sse(
                SSEEvent(event="thinking", data={"message": "Analyzing your design..."})
            ).encode("utf-8")

            # Build previous_messages from session history (user + assistant only)
            previous_messages = [
                {"role": m.role, "content": m.content}
                for m in session.messages
                if m.role in ("user", "assistant")
            ]

            start_time = time.monotonic()
            try:
                output = await orchestrator.run(
                    user_prompt=req.prompt,
                    previous_messages=previous_messages if previous_messages else None,
                )
                breaker.record_success()
            except InterpreterException as e:
                if e.error.code in (
                    ErrorCode.VERTEX_AI_TIMEOUT,
                    ErrorCode.VERTEX_AI_RATE_LIMIT,
                ):
                    breaker.record_failure()
                raise

            elapsed_ms = (time.monotonic() - start_time) * 1000.0

            for ev in output.events:
                if ev.kind == "tool_call" and ev.tool_call is not None:
                    yield serialize_sse(
                        SSEEvent(
                            event="tool_call",
                            data={
                                "tool": ev.tool_call.name,
                                "args": ev.tool_call.args,
                            },
                        )
                    ).encode("utf-8")
                elif ev.kind == "tool_result":
                    continue  # internal; not surfaced to the client

            validate_physical_consistency(output.intent, registry)
            await store.update_intent(
                session.session_id, output.intent, user_overrides={}
            )

            # Append assistant message for multi-turn context
            await store.append_message(
                session.session_id,
                SessionMessage(
                    role="assistant",
                    content=json.dumps(output.intent.model_dump(mode="json")),
                    timestamp=datetime.now(UTC),
                ),
            )

            metrics.request_count_inc(
                status="success",
                language=language,
                intent_type=output.intent.type,
            )
            metrics.latency_ms_record(
                intent_type=output.intent.type,
                value_ms=elapsed_ms,
            )

            logger.info(
                "interpret_request_completed",
                session_id=session.session_id,
                intent_type=output.intent.type,
                latency_ms=int(elapsed_ms),
                retry_count=output.retry_count,
                extracted_fields=sum(
                    1
                    for f in output.intent.fields.values()
                    if f.source == FieldSource.EXTRACTED
                ),
                missing_fields=len(output.intent.missing_field_names()),
            )

            yield serialize_sse(
                SSEEvent(
                    event="final",
                    data=InterpretResponse(
                        session_id=session.session_id,
                        intent=output.intent,
                        language=language,
                    ).model_dump(mode="json"),
                )
            ).encode("utf-8")
        except InterpreterException as e:
            metrics.request_count_inc(
                status="error",
                language=language,
                intent_type="unknown",
            )
            metrics.retry_count_inc(error_code=e.error.code.value)
            logger.warning(
                "interpret_request_failed",
                session_id=session.session_id if session is not None else None,
                error_code=e.error.code.value,
                error_field=e.error.field,
            )
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data=e.error.model_dump(mode="json"),
                )
            ).encode("utf-8")
        except Exception:  # catch-all for unexpected errors
            logger.exception(
                "unhandled_error_in_stream",
                session_id=session.session_id if session is not None else None,
            )
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data=InterpreterError(
                        code=ErrorCode.INTERNAL_ERROR,
                        message="An unexpected error occurred. Please try again.",
                    ).model_dump(mode="json"),
                )
            ).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/interpret/refine", response_model=InterpretResponse)
async def interpret_refine(
    req: RefineRequest, request: Request
) -> InterpretResponse:
    store = request.app.state.session_store
    registry = request.app.state.registry

    try:
        session = await store.load(req.session_id)
    except InterpreterException as e:
        if e.error.code == ErrorCode.SESSION_NOT_FOUND:
            raise HTTPException(status_code=404, detail="Session not found.") from e
        raise
    if session.current_intent is None:
        raise HTTPException(status_code=404, detail="No intent for this session yet.")

    updated = merge_refinement(session.current_intent, req.field_updates)
    try:
        validate_physical_consistency(updated, registry)
    except InterpreterException as e:
        if e.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION:
            raise HTTPException(
                status_code=422,
                detail={
                    "errors": [e.error.model_dump(mode="json")],
                },
            ) from e
        raise

    await store.update_intent(
        req.session_id, updated, user_overrides=session.user_overrides
    )
    return InterpretResponse(
        session_id=req.session_id,
        intent=updated,
        language=session.language,
    )


@router.get("/interpret/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict[str, Any]:
    store = request.app.state.session_store
    session = await store.load(session_id)
    return {"session": session.model_dump(mode="json")}
