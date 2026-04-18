"""Unit tests for GeometryError taxonomy."""
from __future__ import annotations

import pytest

from services.geometry.domain.errors import (
    GeometryError,
    GeometryErrorCode,
    GeometryException,
)


def test_error_code_stable_values() -> None:
    # Part of the HTTP contract — do not change.
    assert GeometryErrorCode.PARAMETER_OUT_OF_RANGE == "parameter_out_of_range"
    assert GeometryErrorCode.UNKNOWN_PRIMITIVE == "unknown_primitive"
    assert GeometryErrorCode.COMPOSITION_RULE_MISSING == "composition_rule_missing"
    assert GeometryErrorCode.MATERIAL_NOT_FOUND == "material_not_found"
    assert GeometryErrorCode.BUILD123D_FAILED == "build123d_failed"
    assert GeometryErrorCode.BOOLEAN_OPERATION_FAILED == "boolean_operation_failed"
    assert GeometryErrorCode.TESSELLATION_FAILED == "tessellation_failed"
    assert GeometryErrorCode.STEP_EXPORT_FAILED == "step_export_failed"
    assert GeometryErrorCode.GLB_EXPORT_FAILED == "glb_export_failed"
    assert GeometryErrorCode.SVG_EXPORT_FAILED == "svg_export_failed"
    assert GeometryErrorCode.GCS_UPLOAD_FAILED == "gcs_upload_failed"
    assert GeometryErrorCode.GCS_UNAVAILABLE == "gcs_unavailable"
    assert GeometryErrorCode.CACHE_READ_FAILED == "cache_read_failed"
    assert GeometryErrorCode.INTERNAL_ERROR == "internal_error"


def test_geometry_error_serializes_to_dict() -> None:
    err = GeometryError(
        code=GeometryErrorCode.BOOLEAN_OPERATION_FAILED,
        message="Boolean union failed for Flywheel_Rim + Shaft",
        primitive="Flywheel_Rim",
        stage="build",
    )
    assert err.model_dump() == {
        "code": "boolean_operation_failed",
        "message": "Boolean union failed for Flywheel_Rim + Shaft",
        "primitive": "Flywheel_Rim",
        "field": None,
        "stage": "build",
        "details": None,
        "retry_after": None,
    }


def test_raise_as_wraps_in_exception() -> None:
    err = GeometryError(
        code=GeometryErrorCode.GCS_UNAVAILABLE,
        message="GCS unreachable",
        retry_after=60,
    )
    with pytest.raises(GeometryException) as exc:
        err.raise_as()
    assert exc.value.error.code == GeometryErrorCode.GCS_UNAVAILABLE
    assert exc.value.error.retry_after == 60
