"""Structured error taxonomy for S4 Explainer."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ExplainErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    GEMMA_TIMEOUT = "gemma_timeout"
    GEMMA_RATE_LIMITED = "gemma_rate_limited"
    GEMMA_FAILED = "gemma_failed"
    REPORT_PARSE_FAILED = "report_parse_failed"
    REPORT_SCHEMA_INVALID = "report_schema_invalid"
    INTERNAL_ERROR = "internal_error"


_STATUS_MAP: dict[ExplainErrorCode, int] = {
    ExplainErrorCode.INVALID_INPUT: 422,
    ExplainErrorCode.GEMMA_TIMEOUT: 504,
    ExplainErrorCode.GEMMA_RATE_LIMITED: 429,
    ExplainErrorCode.GEMMA_FAILED: 502,
    ExplainErrorCode.REPORT_PARSE_FAILED: 500,
    ExplainErrorCode.REPORT_SCHEMA_INVALID: 500,
    ExplainErrorCode.INTERNAL_ERROR: 500,
}


class ExplainError(BaseModel):
    code: ExplainErrorCode
    message: str
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return _STATUS_MAP.get(self.code, 500)

    def raise_as(self) -> None:
        raise ExplainException(self)


class ExplainException(RuntimeError):  # noqa: N818 -- intentional distinction from ExplainError model
    """Raised by generator and router internals; carries an ExplainError payload."""

    def __init__(self, error: ExplainError) -> None:
        super().__init__(error.message)
        self.error = error
