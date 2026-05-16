"""POST /analyze router and FastAPI exception handler."""
from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from services.interpreter.domain.materials import MaterialsCatalog
from services.physics.api.dto import AnalyzeRequest
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode, AnalysisException
from services.physics.domain.models import AnalysisResult
from services.physics.load_case import derive_load_case
from services.physics.solvers_registry import get_solver

_logger = structlog.get_logger("physics.router")
_DEFAULT_MATERIAL = "steel_a36"

router = APIRouter(tags=["physics"])


@router.post("/analyze", response_model=AnalysisResult)
def analyze(request: AnalyzeRequest, app_request: Request) -> AnalysisResult:
    intent = request.intent
    catalog: MaterialsCatalog = app_request.app.state.catalog
    material_name = request.material_name or _DEFAULT_MATERIAL

    try:
        material = catalog.get(material_name)
    except KeyError:
        AnalysisError(
            code=AnalysisErrorCode.MATERIAL_NOT_FOUND,
            message=f"Material {material_name!r} not in catalog",
            intent_type=intent.type,
            field="material_name",
            details={"material_name": material_name},
        ).raise_as()
        raise AssertionError("unreachable") from None  # type-narrowing

    start = time.perf_counter()
    _logger.info(
        "analyze_request_started",
        intent_type=intent.type,
        material=material.name,
    )

    load_case = derive_load_case(intent)
    solver = get_solver(intent.type)
    geometry = _extract_geometry(intent)

    try:
        result = solver(geometry, load_case, material)
    except AnalysisException:
        raise
    except Exception as exc:  # bridge unknown solver failures into AnalysisException
        AnalysisError(
            code=AnalysisErrorCode.SOLVER_FAILED,
            message=f"Solver crashed: {exc!r}",
            intent_type=intent.type,
            details={"exception_type": type(exc).__name__},
        ).raise_as()
        raise AssertionError("unreachable") from exc  # type-narrowing

    _logger.info(
        "analyze_completed",
        intent_type=intent.type,
        material=material.name,
        safety_factor=result.safety_factor,
        verdict=result.verdict.value,
        stress_max_mpa=result.stress_max_pa / 1.0e6,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
    return result


def _extract_geometry(intent: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, field in intent.fields.items():
        if field.value is None:
            continue
        try:
            out[name] = float(field.value)
        except (TypeError, ValueError):
            continue
    return out


def register_physics_router(app: FastAPI) -> None:
    """Attach the physics router and its exception handler to an app."""

    @app.exception_handler(AnalysisException)
    async def _handle_analysis_exception(_req: Request, exc: AnalysisException) -> JSONResponse:
        _logger.warning(
            "analyze_failed",
            code=exc.error.code.value,
            intent_type=exc.error.intent_type,
            field=exc.error.field,
        )
        return JSONResponse(status_code=exc.error.http_status, content=exc.error.model_dump())

    app.include_router(router)
