"""Unit tests for the session store contract (using the local fake)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.fake_store import FakeSessionStore
from services.interpreter.session.store import SessionMessage


@pytest.fixture
def store() -> FakeSessionStore:
    return FakeSessionStore()


async def test_create_and_load_session(store: FakeSessionStore) -> None:
    session = await store.create_session(
        user_id="anonymous", language="en"
    )
    assert session.session_id
    loaded = await store.load(session.session_id)
    assert loaded.session_id == session.session_id
    assert loaded.language == "en"


async def test_load_unknown_session_raises(store: FakeSessionStore) -> None:
    with pytest.raises(InterpreterException) as exc:
        await store.load("nonexistent")
    assert exc.value.error.code == ErrorCode.SESSION_NOT_FOUND


async def test_append_message_persists(store: FakeSessionStore) -> None:
    session = await store.create_session(user_id="u1", language="es")
    await store.append_message(
        session.session_id,
        SessionMessage(
            role="user",
            content="hola",
            timestamp=datetime.now(UTC),
        ),
    )
    loaded = await store.load(session.session_id)
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "hola"


async def test_update_intent_persists(store: FakeSessionStore) -> None:
    session = await store.create_session(user_id="u1", language="en")
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
    )
    await store.update_intent(session.session_id, intent, user_overrides={})
    loaded = await store.load(session.session_id)
    assert loaded.current_intent is not None
    assert loaded.current_intent.type == "Shaft"
