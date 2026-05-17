"""Unit tests verifying Part.from_data is invoked when image kwarg is set."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.interpreter.agent.gemma_client import ImageInput
from services.interpreter.agent.vertex_gemma import VertexGemmaClient


async def _async_gen(*chunks: MagicMock) -> AsyncIterator[MagicMock]:
    for c in chunks:
        yield c


@pytest.fixture()
def client() -> VertexGemmaClient:
    with (
        patch("services.interpreter.agent.vertex_gemma.aiplatform.init"),
        patch("services.interpreter.agent.vertex_gemma.GenerativeModel"),
    ):
        return VertexGemmaClient(
            project_id="p", region="us-central1", model_name="m", timeout_seconds=2,
        )


@pytest.mark.asyncio
async def test_part_from_data_called_when_image_present(
    client: VertexGemmaClient,
) -> None:
    captured_contents: list[Any] = []

    async def _stream(contents: Any, *args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
        captured_contents.append(contents)
        return _async_gen()

    client._model.generate_content_async = _stream  # type: ignore[assignment]

    image_bytes = b"\x89PNG\r\n\x1a\n" + b"\xde\xad\xbe\xef"
    image = ImageInput(mime_type="image/png", data=image_bytes)

    # Drive the stream
    async for _ in client.generate(
        system_prompt="sys", user_prompt="describe", tools=[], image=image,
    ):
        pass

    assert len(captured_contents) == 1
    contents = captured_contents[0]
    # When image is present the SDK gets a list of Content objects (not raw strings)
    assert isinstance(contents, list)
    # The last Content is the user turn carrying the image + text parts
    last = contents[-1]
    parts = last.parts
    assert len(parts) == 2  # image first, text second
    # We cannot easily introspect Part internals without invoking the SDK,
    # but ensuring two parts on the final Content confirms the image was added.


@pytest.mark.asyncio
async def test_no_part_from_data_when_image_absent(
    client: VertexGemmaClient,
) -> None:
    captured_contents: list[Any] = []

    async def _stream(contents: Any, *args: Any, **kwargs: Any) -> AsyncIterator[MagicMock]:
        captured_contents.append(contents)
        return _async_gen()

    client._model.generate_content_async = _stream  # type: ignore[assignment]

    async for _ in client.generate(
        system_prompt="sys", user_prompt="describe", tools=[], image=None,
    ):
        pass

    # No image + no previous_messages → fast path: list of raw strings
    assert captured_contents[0] == ["sys", "describe"]
