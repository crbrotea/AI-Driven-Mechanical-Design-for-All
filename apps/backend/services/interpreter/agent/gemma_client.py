"""Abstraction over Gemma 4 / Vertex AI.

The Protocol allows substituting a scripted stub in tests without
touching the real Vertex AI SDK.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict


class GemmaToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    args: dict[str, Any]


class GemmaEvent(BaseModel):
    """An event emitted by Gemma during generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: Literal["thinking", "tool_call", "tool_result", "final_json", "error"]
    thinking_text: str | None = None
    tool_call: GemmaToolCall | None = None
    tool_result: Any | None = None
    final_json: dict[str, Any] | None = None
    error_message: str | None = None


class GemmaProtocol(Protocol):
    """Abstract Gemma generation API. Real impl uses google-cloud-aiplatform."""

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        ...
