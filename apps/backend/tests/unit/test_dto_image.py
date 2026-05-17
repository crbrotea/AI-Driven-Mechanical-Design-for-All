"""Unit tests for InterpretRequest image_b64 / image_mime fields."""
from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from services.interpreter.api.dto import InterpretRequest


def _b64(n_bytes: int) -> str:
    return base64.b64encode(b"\x89PNG" + b"\x00" * (n_bytes - 4)).decode()


def test_text_only_request_back_compat() -> None:
    req = InterpretRequest(prompt="hello")
    assert req.image_b64 is None
    assert req.image_mime is None


def test_valid_image_request_accepted() -> None:
    payload = _b64(1024)
    req = InterpretRequest(
        prompt="this sketch",
        image_b64=payload,
        image_mime="image/png",
    )
    assert req.image_b64 == payload
    assert req.image_mime == "image/png"


def test_mime_outside_allowlist_rejected() -> None:
    with pytest.raises(ValidationError):
        InterpretRequest(
            prompt="x",
            image_b64=_b64(100),
            image_mime="image/gif",  # type: ignore[arg-type]
        )


def test_only_b64_without_mime_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        InterpretRequest(prompt="x", image_b64=_b64(100))
    assert "image_mime" in str(exc.value) or "both" in str(exc.value).lower()


def test_only_mime_without_b64_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        InterpretRequest(prompt="x", image_mime="image/png")
    assert "image_b64" in str(exc.value) or "both" in str(exc.value).lower()


def test_image_over_4mib_rejected() -> None:
    # 5 MiB of zeros after base64 will decode to 5 MiB binary
    big = base64.b64encode(b"\x00" * (5 * 1024 * 1024)).decode()
    with pytest.raises(ValidationError) as exc:
        InterpretRequest(prompt="x", image_b64=big, image_mime="image/png")
    msg = str(exc.value).lower()
    assert "4" in msg or "size" in msg or "large" in msg or "exceeds" in msg


def test_malformed_base64_rejected() -> None:
    with pytest.raises(ValidationError):
        InterpretRequest(
            prompt="x",
            image_b64="!!!not-valid-base64!!!",
            image_mime="image/png",
        )


def test_image_jpeg_accepted() -> None:
    req = InterpretRequest(prompt="x", image_b64=_b64(100), image_mime="image/jpeg")
    assert req.image_mime == "image/jpeg"


def test_image_webp_accepted() -> None:
    req = InterpretRequest(prompt="x", image_b64=_b64(100), image_mime="image/webp")
    assert req.image_mime == "image/webp"
