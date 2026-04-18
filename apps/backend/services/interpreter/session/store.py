"""Session store contract and Firestore implementation."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from google.cloud import firestore
from pydantic import BaseModel, ConfigDict

from services.interpreter.domain.errors import ErrorCode, InterpreterError
from services.interpreter.domain.intent import DesignIntent, TriStateField


class SessionMessage(BaseModel):
    """A single message in a session conversation history."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime


class Session(BaseModel):
    """Persistent session state."""

    model_config = ConfigDict(frozen=False)

    session_id: str
    user_id: str
    language: Literal["es", "en"]
    created_at: datetime
    updated_at: datetime
    messages: list[SessionMessage] = []
    current_intent: DesignIntent | None = None
    user_overrides: dict[str, TriStateField] = {}


class SessionStore(Protocol):
    """Async session persistence contract."""

    async def create_session(
        self, *, user_id: str, language: Literal["es", "en"]
    ) -> Session: ...

    async def load(self, session_id: str) -> Session: ...

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None: ...

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None: ...

    async def delete(self, session_id: str) -> None: ...


# --- Firestore implementation ---


class FirestoreSessionStore:
    """Google Firestore-backed implementation of SessionStore."""

    COLLECTION = "interpreter_sessions"

    def __init__(self, client: firestore.AsyncClient) -> None:
        self._client = client

    def _collection(self) -> Any:
        return self._client.collection(self.COLLECTION)

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
        await self._collection().document(session.session_id).set(
            session.model_dump(mode="json")
        )
        return session

    async def load(self, session_id: str) -> Session:
        doc = await self._collection().document(session_id).get()
        if not doc.exists:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        return Session.model_validate(doc.to_dict())

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None:
        ref = self._collection().document(session_id)
        snap = await ref.get()
        if not snap.exists:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        await ref.update(
            {
                "messages": firestore.ArrayUnion(
                    [message.model_dump(mode="json")]
                ),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None:
        await self._collection().document(session_id).update(
            {
                "current_intent": intent.model_dump(mode="json"),
                "user_overrides": {
                    k: v.model_dump(mode="json") for k, v in user_overrides.items()
                },
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    async def delete(self, session_id: str) -> None:
        await self._collection().document(session_id).delete()
