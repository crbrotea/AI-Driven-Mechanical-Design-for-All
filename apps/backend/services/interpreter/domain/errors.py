"""Error taxonomy for the Interpreter service.

Codes are part of the HTTP contract and MUST remain stable across versions.
User-facing messages are expected to be localized by the caller.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Stable error codes exposed via HTTP."""

    INVALID_JSON_RETRY_FAILED = "invalid_json_retry_failed"
    UNKNOWN_PRIMITIVE = "unknown_primitive"
    PHYSICAL_RANGE_VIOLATION = "physical_range_violation"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    UNIT_PARSE_FAILED = "unit_parse_failed"
    VERTEX_AI_TIMEOUT = "vertex_ai_timeout"
    VERTEX_AI_RATE_LIMIT = "vertex_ai_rate_limit"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    INTERNAL_ERROR = "internal_error"


class InterpreterError(BaseModel):
    """Structured error returned to clients or raised internally."""

    code: ErrorCode
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None
    retry_after: int | None = Field(
        default=None,
        description="Seconds before the client should retry, if recoverable.",
    )

    def raise_as(self) -> None:
        """Raise this error as a RuntimeError carrying the model."""
        raise InterpreterException(self)


class InterpreterException(RuntimeError):  # noqa: N818
    """Python exception wrapping an InterpreterError for propagation."""

    def __init__(self, error: InterpreterError) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error
