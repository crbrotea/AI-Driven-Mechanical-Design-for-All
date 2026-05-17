"""End-to-end component test: image flows from /interpret → Vertex Part.from_data."""
from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
    ImageInput,
)
from services.interpreter.app import create_app
from services.interpreter.session.fake_store import FakeSessionStore

BACKEND_ROOT = Path(__file__).parent.parent.parent


class _RecordingGemma(GemmaProtocol):
    """Captures the image kwarg so the test can assert on it."""

    def __init__(self) -> None:
        self.received_image: ImageInput | None = None
        self.received_prompt: str | None = None

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
        image: ImageInput | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        self.received_image = image
        self.received_prompt = user_prompt
        yield GemmaEvent(
            kind="final_json",
            final_json={
                "type": "Shaft",
                "fields": {
                    "diameter_m": {"value": 0.05, "source": "extracted"},
                    "length_m": {"value": 0.5, "source": "extracted"},
                },
                "composed_of": [],
            },
        )


@pytest.fixture
def gemma() -> _RecordingGemma:
    return _RecordingGemma()


@pytest.fixture
def client(gemma: _RecordingGemma) -> TestClient:
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=gemma,
        session_store=FakeSessionStore(),
    )
    return TestClient(app)


def test_interpret_without_image_threads_none(
    client: TestClient, gemma: _RecordingGemma
) -> None:
    with client.stream(
        "POST", "/interpret", json={"prompt": "a 5cm shaft 50cm long"}
    ) as response:
        b"".join(response.iter_bytes())
    assert gemma.received_image is None


def test_interpret_with_image_threads_decoded_bytes(
    client: TestClient, gemma: _RecordingGemma
) -> None:
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000
    encoded = base64.b64encode(raw).decode()
    with client.stream(
        "POST",
        "/interpret",
        json={
            "prompt": "use this sketch",
            "image_b64": encoded,
            "image_mime": "image/png",
        },
    ) as response:
        b"".join(response.iter_bytes())
    assert gemma.received_image is not None
    assert gemma.received_image.mime_type == "image/png"
    assert gemma.received_image.data == raw


def test_interpret_rejects_oversize_image(client: TestClient) -> None:
    big = base64.b64encode(b"\x00" * (5 * 1024 * 1024)).decode()
    response = client.post(
        "/interpret",
        json={"prompt": "x", "image_b64": big, "image_mime": "image/png"},
    )
    assert response.status_code == 422
