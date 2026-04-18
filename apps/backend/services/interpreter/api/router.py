"""FastAPI router for the Interpreter endpoints."""
from __future__ import annotations

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
    InterpreterException,
)
from services.interpreter.domain.validators import validate_physical_consistency
from services.interpreter.session.merge import merge_refinement
from services.interpreter.session.store import Session, SessionMessage

router = APIRouter()


def _detect_language(text: str) -> Literal["es", "en"]:
    # Minimal heuristic; replaced by Gemma-reported language post-generation.
    es_markers = {"diseña", "necesito", "un ", "una ", "con ", "para "}
    lower = text.lower()
    return "es" if any(m in lower for m in es_markers) else "en"


@router.post("/interpret")
async def interpret(req: InterpretRequest, request: Request) -> StreamingResponse:
    orchestrator: Orchestrator = request.app.state.orchestrator
    store = request.app.state.session_store
    registry = request.app.state.registry

    language = _detect_language(req.prompt)

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            session: Session
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

            yield serialize_sse(
                SSEEvent(event="thinking", data={"message": "Analyzing your design..."})
            ).encode("utf-8")

            output = await orchestrator.run(user_prompt=req.prompt)

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
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data=e.error.model_dump(mode="json"),
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

    session = await store.load(req.session_id)
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
