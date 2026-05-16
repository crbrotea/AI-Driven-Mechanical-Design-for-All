"""Documenter error taxonomy tests."""
from __future__ import annotations

import json

import pytest

from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
    DocumentException,
)


def test_codes_stable() -> None:
    assert DocumentErrorCode.INVALID_INPUT.value == "invalid_input"
    assert DocumentErrorCode.GEOMETRY_REBUILD_FAILED.value == "geometry_rebuild_failed"
    assert DocumentErrorCode.VIEW_PROJECTION_FAILED.value == "view_projection_failed"
    assert DocumentErrorCode.REPORT_BUILD_FAILED.value == "report_build_failed"
    assert DocumentErrorCode.DRAWING_BUILD_FAILED.value == "drawing_build_failed"
    assert DocumentErrorCode.GCS_UPLOAD_FAILED.value == "gcs_upload_failed"
    assert DocumentErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_http_status_mapping() -> None:
    assert DocumentError(code=DocumentErrorCode.INVALID_INPUT, message="x").http_status == 422
    assert DocumentError(code=DocumentErrorCode.GCS_UPLOAD_FAILED, message="x").http_status == 502
    assert DocumentError(code=DocumentErrorCode.REPORT_BUILD_FAILED, message="x").http_status == 500
    assert DocumentError(code=DocumentErrorCode.INTERNAL_ERROR, message="x").http_status == 500


def test_serializes_with_optional_fields() -> None:
    err = DocumentError(
        code=DocumentErrorCode.GCS_UPLOAD_FAILED,
        message="upload broke",
        stage="upload",
        retry_after=5,
    )
    payload = json.loads(err.model_dump_json())
    assert payload["code"] == "gcs_upload_failed"
    assert payload["stage"] == "upload"
    assert payload["retry_after"] == 5


def test_raise_as_wraps_in_exception() -> None:
    err = DocumentError(code=DocumentErrorCode.REPORT_BUILD_FAILED, message="boom")
    with pytest.raises(DocumentException) as ei:
        err.raise_as()
    assert ei.value.error.code is DocumentErrorCode.REPORT_BUILD_FAILED
