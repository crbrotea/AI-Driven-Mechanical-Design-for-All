"""Structured error taxonomy for S5 Documenter."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class DocumentErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    GEOMETRY_REBUILD_FAILED = "geometry_rebuild_failed"
    VIEW_PROJECTION_FAILED = "view_projection_failed"
    REPORT_BUILD_FAILED = "report_build_failed"
    DRAWING_BUILD_FAILED = "drawing_build_failed"
    GCS_UPLOAD_FAILED = "gcs_upload_failed"
    INTERNAL_ERROR = "internal_error"


_STATUS_MAP: dict[DocumentErrorCode, int] = {
    DocumentErrorCode.INVALID_INPUT: 422,
    DocumentErrorCode.GEOMETRY_REBUILD_FAILED: 500,
    DocumentErrorCode.VIEW_PROJECTION_FAILED: 500,
    DocumentErrorCode.REPORT_BUILD_FAILED: 500,
    DocumentErrorCode.DRAWING_BUILD_FAILED: 500,
    DocumentErrorCode.GCS_UPLOAD_FAILED: 502,
    DocumentErrorCode.INTERNAL_ERROR: 500,
}


class DocumentError(BaseModel):
    code: DocumentErrorCode
    message: str
    field: str | None = None
    stage: str | None = None
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return _STATUS_MAP.get(self.code, 500)

    def raise_as(self) -> None:
        raise DocumentException(self)


class DocumentException(RuntimeError):  # noqa: N818 -- intentional distinction from DocumentError model
    """Raised by pipeline internals; carries a DocumentError payload."""

    def __init__(self, error: DocumentError) -> None:
        super().__init__(error.message)
        self.error = error
