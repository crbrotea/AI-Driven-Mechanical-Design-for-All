"""Per-error retry policy. Max 1 retry per error type."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from services.interpreter.domain.errors import ErrorCode


class RetryStrategy(StrEnum):
    CORRECTIVE_PROMPT = "corrective_prompt"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FAIL_FAST = "fail_fast"
    RETURN_TO_USER = "return_to_user"


class RetryDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    should_retry: bool
    strategy: RetryStrategy
    backoff_s: float = 0.0


_POLICY: dict[ErrorCode, tuple[int, RetryStrategy]] = {
    ErrorCode.INVALID_JSON_RETRY_FAILED: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.UNKNOWN_PRIMITIVE: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.VERTEX_AI_TIMEOUT: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.VERTEX_AI_RATE_LIMIT: (1, RetryStrategy.EXPONENTIAL_BACKOFF),
    ErrorCode.PHYSICAL_RANGE_VIOLATION: (0, RetryStrategy.RETURN_TO_USER),
    ErrorCode.AMBIGUOUS_INTENT: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.UNIT_PARSE_FAILED: (0, RetryStrategy.RETURN_TO_USER),
    ErrorCode.SESSION_NOT_FOUND: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.SESSION_EXPIRED: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.INTERNAL_ERROR: (0, RetryStrategy.FAIL_FAST),
}


def decide(*, error_code: ErrorCode, attempt: int) -> RetryDecision:
    """Return whether to retry given the error and attempt number (0-indexed)."""
    max_retries, strategy = _POLICY.get(
        error_code, (0, RetryStrategy.FAIL_FAST)
    )
    if attempt >= max_retries:
        return RetryDecision(should_retry=False, strategy=strategy)
    backoff = 0.0
    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        backoff = 2.0 ** attempt  # 1.0s, 2.0s, ...
    return RetryDecision(
        should_retry=True, strategy=strategy, backoff_s=backoff
    )
