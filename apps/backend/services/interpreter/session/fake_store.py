"""In-memory implementation of SessionStore for unit/component tests."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)
from services.interpreter.domain.intent import DesignIntent, TriStateField
from services.interpreter.session.store import Session, SessionMessage


class FakeSessionStore:
    """Thread-unsafe in-memory session store for tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self, *, user_id: str, language: Literal["es", "en"]
    ) -> Session:
        now = datetime.now(UTC)
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            language=language,
            created_at=now,
            updated_at=now,
        )
        self._sessions[session.session_id] = session
        return session

    async def load(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        return self._sessions[session_id]

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None:
        session = await self.load(session_id)
        session.messages.append(message)
        session.updated_at = datetime.now(UTC)

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None:
        session = await self.load(session_id)
        session.current_intent = intent
        session.user_overrides = dict(user_overrides)
        session.updated_at = datetime.now(UTC)

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
