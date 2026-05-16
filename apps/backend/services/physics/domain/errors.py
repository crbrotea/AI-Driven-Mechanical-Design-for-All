"""Structured error taxonomy for S3 Physics."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class AnalysisErrorCode(StrEnum):
    UNSUPPORTED_INTENT_TYPE = "unsupported_intent_type"
    MATERIAL_NOT_FOUND = "material_not_found"
    MISSING_GEOMETRY_FIELD = "missing_geometry_field"
    MISSING_LOAD_PARAMETER = "missing_load_parameter"
    INVALID_LOAD_VALUE = "invalid_load_value"
    SOLVER_FAILED = "solver_failed"
    NUMERICAL_OVERFLOW = "numerical_overflow"
    INTERNAL_ERROR = "internal_error"


_PRE_SOLVE_CODES: frozenset[AnalysisErrorCode] = frozenset(
    {
        AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE,
        AnalysisErrorCode.MATERIAL_NOT_FOUND,
        AnalysisErrorCode.MISSING_GEOMETRY_FIELD,
        AnalysisErrorCode.MISSING_LOAD_PARAMETER,
        AnalysisErrorCode.INVALID_LOAD_VALUE,
    }
)


class AnalysisError(BaseModel):
    code: AnalysisErrorCode
    message: str
    intent_type: str | None = None
    field: str | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return 422 if self.code in _PRE_SOLVE_CODES else 500

    def raise_as(self) -> None:
        raise AnalysisException(self)


class AnalysisException(RuntimeError):
    """Raised by solvers and router internals; carries an AnalysisError payload."""

    def __init__(self, error: AnalysisError) -> None:
        super().__init__(error.message)
        self.error = error
