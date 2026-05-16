"""Real Gemma 4 client using google-cloud-aiplatform Vertex AI SDK."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from google.api_core import exceptions as google_exc
from google.cloud import aiplatform
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaToolCall,
    VertexRateLimited,
    VertexTimeout,
)
from services.interpreter.domain.errors import ErrorCode, InterpreterError


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
        timeout_seconds: int = 10,
    ) -> None:
        aiplatform.init(project=project_id, location=region)
        self._model = GenerativeModel(model_name)
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_s = timeout_seconds

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        previous_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        declarations = [FunctionDeclaration(**t) for t in tools]
        vertex_tools = [Tool(function_declarations=declarations)] if declarations else []

        # Build content list: system prompt + history + new user turn.
        # Vertex SDK rejects a list that mixes raw strings with Content
        # objects, so when previous_messages is non-empty we wrap every item.
        if previous_messages:
            contents: list[Any] = [
                Content(role="user", parts=[Part.from_text(system_prompt)])
            ]
            for msg in previous_messages:
                role = msg.get("role", "user")
                text = msg.get("content", "")
                contents.append(
                    Content(role=role, parts=[Part.from_text(text)])
                )
            contents.append(
                Content(role="user", parts=[Part.from_text(user_prompt)])
            )
        else:
            contents = [system_prompt, user_prompt]

        # If tools are disabled, force JSON output to ensure the model produces
        # a single parseable response (no chatty preamble).
        gen_config: dict[str, Any] = {
            "temperature": self._temperature,
            "max_output_tokens": self._max_output_tokens,
        }
        if not vertex_tools:
            gen_config["response_mime_type"] = "application/json"

        try:
            stream = await asyncio.wait_for(
                self._model.generate_content_async(
                    contents,
                    tools=vertex_tools or None,
                    generation_config=gen_config,
                    stream=True,
                ),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            InterpreterError(
                code=ErrorCode.VERTEX_AI_TIMEOUT,
                message="Vertex AI request timed out before streaming started.",
            ).raise_as()
            return  # unreachable — satisfies type checker
        except google_exc.DeadlineExceeded as exc:
            InterpreterError(
                code=ErrorCode.VERTEX_AI_TIMEOUT,
                message=f"Vertex AI deadline exceeded: {exc}",
            ).raise_as()
            return
        except google_exc.ResourceExhausted as exc:
            InterpreterError(
                code=ErrorCode.VERTEX_AI_RATE_LIMIT,
                message=f"Vertex AI quota exhausted: {exc}",
            ).raise_as()
            return
        except google_exc.ServiceUnavailable as exc:
            InterpreterError(
                code=ErrorCode.VERTEX_AI_TIMEOUT,
                message=f"Vertex AI service unavailable: {exc}",
            ).raise_as()
            return
        except (KeyError, TypeError, AttributeError):
            raise  # programming errors — let them propagate for visibility
        except Exception as exc:
            InterpreterError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Unexpected error calling Vertex AI: {exc}",
            ).raise_as()
            return

        # Accumulate text chunks across the stream so we can JSON-parse once
        # at the end. Tool calls emit immediately (one per part).
        accumulated_text = ""
        async for chunk in stream:
            for candidate in chunk.candidates:
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
                        accumulated_text += part.text

        if accumulated_text.strip():
            cleaned = _strip_codefence(accumulated_text)
            try:
                parsed: dict[str, Any] = json.loads(cleaned)
                yield GemmaEvent(kind="final_json", final_json=parsed)
            except json.JSONDecodeError:
                yield GemmaEvent(
                    kind="error",
                    error_message=f"Non-JSON final content: {accumulated_text[:200]}",
                )

    async def generate_text_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        """Plain text streaming, no tools. Yields raw text chunks.

        Uses response_mime_type='application/json' so Gemma produces JSON
        directly. The caller is responsible for parsing the accumulated text.
        """
        contents: list[Any] = [system_prompt, user_prompt]
        try:
            stream = await asyncio.wait_for(
                self._model.generate_content_async(
                    contents,
                    generation_config={
                        "temperature": self._temperature,
                        "max_output_tokens": self._max_output_tokens,
                        "response_mime_type": "application/json",
                    },
                    stream=True,
                ),
                timeout=self._timeout_s,
            )
        except TimeoutError as exc:
            raise VertexTimeout("Vertex AI text streaming timed out") from exc
        except google_exc.ResourceExhausted as exc:
            raise VertexRateLimited(f"Vertex AI quota exhausted: {exc}") from exc

        async for chunk in stream:
            for candidate in chunk.candidates:
                for part in candidate.content.parts:
                    text = getattr(part, "text", "")
                    if text:
                        yield text


def _strip_codefence(text: str) -> str:
    """Remove ```json ... ``` wrappers some Gemini models emit around JSON."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
    if s.startswith("json\n"):
        s = s[5:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()
