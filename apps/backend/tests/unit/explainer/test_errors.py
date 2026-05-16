"""Explainer error taxonomy tests."""
from __future__ import annotations

import json

import pytest

from services.explainer.domain.errors import (
    ExplainError,
    ExplainErrorCode,
    ExplainException,
)


def test_codes_stable() -> None:
    assert ExplainErrorCode.INVALID_INPUT.value == "invalid_input"
    assert ExplainErrorCode.GEMMA_TIMEOUT.value == "gemma_timeout"
    assert ExplainErrorCode.GEMMA_RATE_LIMITED.value == "gemma_rate_limited"
    assert ExplainErrorCode.GEMMA_FAILED.value == "gemma_failed"
    assert ExplainErrorCode.REPORT_PARSE_FAILED.value == "report_parse_failed"
    assert ExplainErrorCode.REPORT_SCHEMA_INVALID.value == "report_schema_invalid"
    assert ExplainErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_http_status_mapping() -> None:
    assert ExplainError(code=ExplainErrorCode.INVALID_INPUT, message="x").http_status == 422
    assert ExplainError(code=ExplainErrorCode.GEMMA_TIMEOUT, message="x").http_status == 504
    assert ExplainError(code=ExplainErrorCode.GEMMA_RATE_LIMITED, message="x").http_status == 429
    assert ExplainError(code=ExplainErrorCode.REPORT_PARSE_FAILED, message="x").http_status == 500
    assert ExplainError(code=ExplainErrorCode.INTERNAL_ERROR, message="x").http_status == 500


def test_serializes() -> None:
    err = ExplainError(
        code=ExplainErrorCode.GEMMA_TIMEOUT,
        message="timed out",
        retry_after=5,
    )
    payload = json.loads(err.model_dump_json())
    assert payload["code"] == "gemma_timeout"
    assert payload["retry_after"] == 5


def test_raise_as_wraps_in_exception() -> None:
    err = ExplainError(code=ExplainErrorCode.REPORT_PARSE_FAILED, message="bad json")
    with pytest.raises(ExplainException) as ei:
        err.raise_as()
    assert ei.value.error.code is ExplainErrorCode.REPORT_PARSE_FAILED
