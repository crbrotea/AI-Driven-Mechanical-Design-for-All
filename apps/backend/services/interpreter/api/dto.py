"""HTTP request/response DTOs for the Interpreter API."""
from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.interpreter.domain.intent import DesignIntent

_MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MiB decoded
ImageMime = Literal["image/png", "image/jpeg", "image/webp"]


class InterpretRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    image_b64: str | None = Field(default=None, max_length=8_000_000)
    image_mime: ImageMime | None = None

    @model_validator(mode="after")
    def _validate_image(self) -> InterpretRequest:
        if (self.image_b64 is None) != (self.image_mime is None):
            raise ValueError(
                "image_b64 and image_mime must both be set or both be absent"
            )
        if self.image_b64 is not None:
            try:
                decoded = base64.b64decode(self.image_b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError(f"image_b64 is not valid base64: {exc}") from exc
            if len(decoded) > _MAX_IMAGE_BYTES:
                raise ValueError(
                    f"image exceeds 4 MiB limit (got {len(decoded)} bytes)"
                )
        return self


class RefineRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    field_updates: dict[str, Any]


class InterpretResponse(BaseModel):
    """Body of the `final` SSE event and the GET /sessions response."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    intent: DesignIntent
    language: str  # "es" | "en"
