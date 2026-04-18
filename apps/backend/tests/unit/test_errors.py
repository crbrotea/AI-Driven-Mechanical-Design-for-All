"""Unit tests for InterpreterError taxonomy."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)


def test_error_code_stable_values() -> None:
    # These string values are part of the HTTP contract — do not change.
    assert ErrorCode.INVALID_JSON_RETRY_FAILED == "invalid_json_retry_failed"
    assert ErrorCode.UNKNOWN_PRIMITIVE == "unknown_primitive"
    assert ErrorCode.PHYSICAL_RANGE_VIOLATION == "physical_range_violation"
    assert ErrorCode.AMBIGUOUS_INTENT == "ambiguous_intent"
    assert ErrorCode.UNIT_PARSE_FAILED == "unit_parse_failed"
    assert ErrorCode.VERTEX_AI_TIMEOUT == "vertex_ai_timeout"
    assert ErrorCode.VERTEX_AI_RATE_LIMIT == "vertex_ai_rate_limit"
    assert ErrorCode.SESSION_NOT_FOUND == "session_not_found"
    assert ErrorCode.SESSION_EXPIRED == "session_expired"
    assert ErrorCode.INTERNAL_ERROR == "internal_error"


def test_interpreter_error_serializes_to_dict() -> None:
    err = InterpreterError(
        code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
        message="inner_diameter must be smaller than outer_diameter",
        field="inner_diameter_m",
    )

    assert err.model_dump() == {
        "code": "physical_range_violation",
        "message": "inner_diameter must be smaller than outer_diameter",
        "field": "inner_diameter_m",
        "details": None,
        "retry_after": None,
    }


def test_interpreter_error_raises_with_retry_after() -> None:
    err = InterpreterError(
        code=ErrorCode.VERTEX_AI_RATE_LIMIT,
        message="Rate limited",
        retry_after=30,
    )
    with pytest.raises(RuntimeError):
        err.raise_as()
