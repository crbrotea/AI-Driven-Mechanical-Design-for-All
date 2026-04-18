"""Error taxonomy for the Geometry service.

Codes are part of the HTTP contract and MUST remain stable across versions.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class GeometryErrorCode(StrEnum):
    """Stable error codes exposed via HTTP and SSE."""

    # Pre-build (422)
    PARAMETER_OUT_OF_RANGE = "parameter_out_of_range"
    UNKNOWN_PRIMITIVE = "unknown_primitive"
    COMPOSITION_RULE_MISSING = "composition_rule_missing"
    MATERIAL_NOT_FOUND = "material_not_found"

    # Build-time (SSE error event)
    BUILD123D_FAILED = "build123d_failed"
    BOOLEAN_OPERATION_FAILED = "boolean_operation_failed"
    TESSELLATION_FAILED = "tessellation_failed"

    # Export
    STEP_EXPORT_FAILED = "step_export_failed"
    GLB_EXPORT_FAILED = "glb_export_failed"
    SVG_EXPORT_FAILED = "svg_export_failed"

    # Infrastructure (retriable)
    GCS_UPLOAD_FAILED = "gcs_upload_failed"
    GCS_UNAVAILABLE = "gcs_unavailable"
    CACHE_READ_FAILED = "cache_read_failed"

    # Catch-all
    INTERNAL_ERROR = "internal_error"


class GeometryError(BaseModel):
    """Structured error returned to clients or raised internally."""

    code: GeometryErrorCode
    message: str
    primitive: str | None = None
    field: str | None = None
    stage: Literal["validate", "build", "export", "upload"] | None = None
    details: dict[str, Any] | None = None
    retry_after: int | None = Field(
        default=None,
        description="Seconds before the client should retry, if recoverable.",
    )

    def raise_as(self) -> None:
        raise GeometryException(self)


class GeometryException(RuntimeError):  # noqa: N818 -- intentional distinction from GeometryError model
    """Python exception wrapping a GeometryError for propagation."""

    def __init__(self, error: GeometryError) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error
