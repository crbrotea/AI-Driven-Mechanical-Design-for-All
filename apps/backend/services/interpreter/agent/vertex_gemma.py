"""Real Gemma 4 client using google-cloud-aiplatform Vertex AI SDK."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from google.cloud import aiplatform
from vertexai.generative_models import (
    FunctionDeclaration,
    GenerativeModel,
    Tool,
)

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaToolCall,
)


class VertexGemmaClient:
    """Real implementation backed by Vertex AI."""

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        model_name: str,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> None:
        aiplatform.init(project=project_id, location=region)
        self._model = GenerativeModel(model_name)
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        declarations = [FunctionDeclaration(**t) for t in tools]
        vertex_tools = [Tool(function_declarations=declarations)]

        response = await self._model.generate_content_async(
            [system_prompt, user_prompt],  # type: ignore[arg-type]
            tools=vertex_tools,
            generation_config={
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        )

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    yield GemmaEvent(
                        kind="tool_call",
                        tool_call=GemmaToolCall(
                            name=part.function_call.name,
                            args=dict(part.function_call.args),
                        ),
                    )
                elif hasattr(part, "text") and part.text:
                    try:
                        parsed: dict[str, Any] = json.loads(part.text)
                        yield GemmaEvent(kind="final_json", final_json=parsed)
                    except json.JSONDecodeError:
                        yield GemmaEvent(
                            kind="error",
                            error_message=f"Non-JSON final content: {part.text[:100]}",
                        )
