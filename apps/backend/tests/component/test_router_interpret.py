"""Component tests for POST /interpret streaming endpoint."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
    GemmaToolCall,
)
from services.interpreter.app import create_app
from services.interpreter.session.fake_store import FakeSessionStore

BACKEND_ROOT = Path(__file__).parent.parent.parent


class _StubGemma(GemmaProtocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        yield GemmaEvent(
            kind="tool_call",
            tool_call=GemmaToolCall(name="list_primitives", args={}),
        )
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
def client() -> TestClient:
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_StubGemma(),
        session_store=FakeSessionStore(),
    )
    return TestClient(app)


def test_interpret_returns_sse_stream(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/interpret",
        json={"prompt": "a 5cm shaft 50cm long"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")
        assert "event: tool_call" in body
        assert "event: final" in body
        assert '"type":"Shaft"' in body


def test_interpret_validation_error_on_empty_prompt(client: TestClient) -> None:
    response = client.post("/interpret", json={"prompt": ""})
    assert response.status_code == 422
