"""Error taxonomy tests."""
from __future__ import annotations

import json

import pytest

from services.physics.domain.errors import (
    AnalysisError,
    AnalysisErrorCode,
    AnalysisException,
)


def test_error_codes_stable() -> None:
    assert AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE.value == "unsupported_intent_type"
    assert AnalysisErrorCode.MATERIAL_NOT_FOUND.value == "material_not_found"
    assert AnalysisErrorCode.MISSING_GEOMETRY_FIELD.value == "missing_geometry_field"
    assert AnalysisErrorCode.MISSING_LOAD_PARAMETER.value == "missing_load_parameter"
    assert AnalysisErrorCode.INVALID_LOAD_VALUE.value == "invalid_load_value"
    assert AnalysisErrorCode.SOLVER_FAILED.value == "solver_failed"
    assert AnalysisErrorCode.NUMERICAL_OVERFLOW.value == "numerical_overflow"
    assert AnalysisErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_error_serializes() -> None:
    err = AnalysisError(
        code=AnalysisErrorCode.MISSING_LOAD_PARAMETER,
        message="rpm is required for Flywheel_Rim",
        intent_type="Flywheel_Rim",
        field="rpm",
    )
    payload = json.loads(err.model_dump_json())
    assert payload["code"] == "missing_load_parameter"
    assert payload["intent_type"] == "Flywheel_Rim"
    assert payload["field"] == "rpm"


def test_raise_as_wraps_in_exception() -> None:
    err = AnalysisError(code=AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE, message="x")
    with pytest.raises(AnalysisException) as ei:
        err.raise_as()
    assert ei.value.error.code is AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE
