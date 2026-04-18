"""Component tests for /interpret/refine and GET /sessions."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
)
from services.interpreter.app import create_app
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.fake_store import FakeSessionStore

BACKEND_ROOT = Path(__file__).parent.parent.parent


class _NullGemma(GemmaProtocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        # not used in these tests
        if False:
            yield GemmaEvent(kind="error", error_message="unused")


@pytest.fixture
def client_and_store() -> tuple[TestClient, FakeSessionStore]:
    store = FakeSessionStore()
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_NullGemma(),
        session_store=store,
    )
    return TestClient(app), store


async def _seed_session_with_intent(store: FakeSessionStore) -> str:
    session = await store.create_session(user_id="u1", language="en")
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
            "length_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
        },
    )
    await store.update_intent(session.session_id, intent, user_overrides={})
    return session.session_id


async def test_refine_applies_field_updates(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    response = client.post(
        "/interpret/refine",
        json={"session_id": session_id, "field_updates": {"diameter_m": 0.08}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"]["fields"]["diameter_m"]["value"] == 0.08
    assert body["intent"]["fields"]["diameter_m"]["source"] == "user"


async def test_refine_returns_422_on_invalid_range(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    # diameter max is 1.0m; 2.0 is out of range.
    response = client.post(
        "/interpret/refine",
        json={"session_id": session_id, "field_updates": {"diameter_m": 2.0}},
    )
    assert response.status_code == 422


async def test_refine_returns_404_on_unknown_session(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, _ = client_and_store
    response = client.post(
        "/interpret/refine",
        json={"session_id": "nonexistent", "field_updates": {}},
    )
    assert response.status_code == 404


async def test_get_session_returns_state(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    response = client.get(f"/interpret/sessions/{session_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == session_id
    assert body["session"]["current_intent"]["type"] == "Shaft"
