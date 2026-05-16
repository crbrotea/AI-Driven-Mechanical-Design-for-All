"""Deterministic in-process stand-in for VertexGemmaClient.generate_text_streaming.

Each constructor accepts a list of "calls", where each call is a list of text
chunks the fake will yield. Use this to script malformed/valid JSON sequences
and exception injection for retry tests.
"""
from __future__ import annotations

from collections.abc import AsyncIterator


class FakeGemmaTextClient:
    def __init__(
        self,
        chunks_per_call: list[list[str]],
        raise_on_first: Exception | None = None,
    ) -> None:
        if not chunks_per_call:
            raise ValueError("chunks_per_call must be non-empty")
        self._chunks_per_call = chunks_per_call
        self._call_count = 0
        self._raise_first = raise_on_first

    @property
    def call_count(self) -> int:
        return self._call_count

    async def generate_text_streaming(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]:
        del system_prompt, user_prompt  # not used by fake, signature must match real client
        self._call_count += 1
        if self._call_count == 1 and self._raise_first is not None:
            raise self._raise_first
        idx = min(self._call_count - 1, len(self._chunks_per_call) - 1)
        for chunk in self._chunks_per_call[idx]:
            yield chunk
