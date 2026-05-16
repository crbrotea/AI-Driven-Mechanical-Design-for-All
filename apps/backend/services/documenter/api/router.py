"""POST /document router for S5 Documenter."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from services.documenter.domain.errors import DocumentException
from services.documenter.domain.models import Deliverables, DocumentRequest
from services.documenter.pipeline import Documenter

_logger = structlog.get_logger("documenter.router")

router = APIRouter(tags=["documenter"])


@router.post("/document", response_model=Deliverables)
async def document(req: DocumentRequest, app_req: Request) -> Deliverables:
    docter: Documenter = app_req.app.state.documenter
    _logger.info(
        "document_request_started",
        intent_type=req.intent.type,
        verdict=req.analysis_result.verdict.value,
        session_id=req.session_id,
    )
    deliv = await docter.document(req)
    _logger.info(
        "document_completed",
        cache_key=deliv.cache_key,
        cache_hit=deliv.cache_hit,
    )
    return deliv


def register_documenter_router(app: FastAPI) -> None:
    """Attach the documenter router and its exception handler to the app."""

    @app.exception_handler(DocumentException)
    async def _handle_doc_exception(_req: Request, exc: DocumentException) -> JSONResponse:
        _logger.warning(
            "document_failed",
            code=exc.error.code.value,
            stage=exc.error.stage,
            field=exc.error.field,
        )
        return JSONResponse(
            status_code=exc.error.http_status,
            content=exc.error.model_dump(),
        )

    app.include_router(router)
