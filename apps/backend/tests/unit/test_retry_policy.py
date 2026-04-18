"""Unit tests for retry policy."""
from __future__ import annotations

from services.interpreter.agent.retry_policy import (
    RetryDecision,
    RetryStrategy,
    decide,
)
from services.interpreter.domain.errors import ErrorCode


def test_invalid_json_retries_once_with_corrective_prompt() -> None:
    d = decide(error_code=ErrorCode.INVALID_JSON_RETRY_FAILED, attempt=0)
    assert d == RetryDecision(
        should_retry=True, strategy=RetryStrategy.CORRECTIVE_PROMPT, backoff_s=0.0
    )


def test_invalid_json_does_not_retry_twice() -> None:
    d = decide(error_code=ErrorCode.INVALID_JSON_RETRY_FAILED, attempt=1)
    assert d.should_retry is False


def test_vertex_rate_limit_uses_exponential_backoff() -> None:
    d = decide(error_code=ErrorCode.VERTEX_AI_RATE_LIMIT, attempt=0)
    assert d.should_retry is True
    assert d.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    assert d.backoff_s > 0.0


def test_vertex_timeout_does_not_retry() -> None:
    d = decide(error_code=ErrorCode.VERTEX_AI_TIMEOUT, attempt=0)
    assert d.should_retry is False
    assert d.strategy == RetryStrategy.FAIL_FAST


def test_physical_range_does_not_retry_returns_to_user() -> None:
    d = decide(error_code=ErrorCode.PHYSICAL_RANGE_VIOLATION, attempt=0)
    assert d.should_retry is False
    assert d.strategy == RetryStrategy.RETURN_TO_USER


def test_unknown_primitive_retries_once_with_corrective() -> None:
    d = decide(error_code=ErrorCode.UNKNOWN_PRIMITIVE, attempt=0)
    assert d.should_retry is True
    assert d.strategy == RetryStrategy.CORRECTIVE_PROMPT
