"""Agent orchestrator: runs Gemma, handles tool calls, applies retry policy."""
from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict

from services.interpreter.agent.gemma_client import GemmaEvent, GemmaProtocol
from services.interpreter.agent.retry_policy import (
    RetryStrategy,
    decide,
)
from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
    InterpreterException,
)
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.primitives_registry import (
    PrimitivesRegistry,
)
from services.interpreter.tools.registry import ToolRegistry


class OrchestratorOutput(BaseModel):
    """Full output of an orchestrator run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    intent: DesignIntent
    events: list[GemmaEvent]
    retry_count: int


_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_primitives",
        "description": "List all registered primitives.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_primitive_schema",
        "description": "Get the full parameter schema of a primitive by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "search_materials",
        "description": "Filter the materials catalog by criteria.",
        "parameters": {
            "type": "object",
            "properties": {"criteria": {"type": "object"}},
            "required": ["criteria"],
        },
    },
    {
        "name": "get_material_properties",
        "description": "Get full properties of a material by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]


class Orchestrator:
    """Coordinates Gemma generation, tool dispatch, and retries."""

    def __init__(
        self,
        *,
        gemma: GemmaProtocol,
        tools: ToolRegistry,
        system_prompt: str,
        registry: PrimitivesRegistry | None = None,
    ) -> None:
        self._gemma = gemma
        self._tools = tools
        self._system_prompt = system_prompt
        self._registry = registry

    async def run(self, *, user_prompt: str) -> OrchestratorOutput:
        """Execute the agent loop until a valid final_json is produced.

        Retries once per recoverable error (per retry_policy).
        """
        events: list[GemmaEvent] = []
        last_error: InterpreterError | None = None
        retry_count = 0
        for attempt in range(2):  # 1 initial + up to 1 retry
            attempt_events, final_json, error = await self._single_attempt(
                user_prompt=user_prompt,
                corrective_context=(
                    self._corrective_message(last_error) if last_error else None
                ),
            )
            events.extend(attempt_events)
            if error is None and final_json is not None:
                intent = self._build_intent(final_json)
                return OrchestratorOutput(
                    intent=intent, events=events, retry_count=retry_count
                )
            last_error = error
            decision = decide(
                error_code=error.code if error else ErrorCode.INTERNAL_ERROR,
                attempt=attempt,
            )
            if not decision.should_retry:
                break
            if decision.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                await asyncio.sleep(decision.backoff_s)
            retry_count = attempt + 1

        if last_error is None:
            last_error = InterpreterError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Orchestrator exited without producing an intent.",
            )
        raise InterpreterException(last_error)

    async def _single_attempt(
        self, *, user_prompt: str, corrective_context: str | None
    ) -> tuple[list[GemmaEvent], dict[str, Any] | None, InterpreterError | None]:
        collected: list[GemmaEvent] = []
        system = self._system_prompt
        if corrective_context:
            system = f"{system}\n\n## Correction\n{corrective_context}"

        final_json: dict[str, Any] | None = None
        async for ev in self._gemma.generate(
            system_prompt=system,
            user_prompt=user_prompt,
            tools=_TOOL_SCHEMAS,
        ):
            collected.append(ev)
            if ev.kind == "tool_call" and ev.tool_call is not None:
                try:
                    result = self._tools.invoke(
                        ev.tool_call.name, ev.tool_call.args
                    )
                except KeyError as e:
                    return collected, None, InterpreterError(
                        code=ErrorCode.UNKNOWN_PRIMITIVE,
                        message=str(e),
                    )
                collected.append(
                    GemmaEvent(
                        kind="tool_result",
                        tool_call=ev.tool_call,
                        tool_result=result,
                    )
                )
            elif ev.kind == "final_json":
                final_json = ev.final_json
            elif ev.kind == "error":
                return collected, None, InterpreterError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=ev.error_message or "gemma error",
                )

        if final_json is None:
            return collected, None, InterpreterError(
                code=ErrorCode.INVALID_JSON_RETRY_FAILED,
                message="Gemma ended without a final_json event.",
            )

        # Validate referenced primitive is known.
        if self._registry is not None:
            try:
                self._registry.get(final_json.get("type", ""))
            except KeyError:
                return collected, None, InterpreterError(
                    code=ErrorCode.UNKNOWN_PRIMITIVE,
                    message=f"Primitive '{final_json.get('type')}' does not exist.",
                )
        return collected, final_json, None

    def _build_intent(self, final_json: dict[str, Any]) -> DesignIntent:
        return DesignIntent.model_validate(final_json)

    def _corrective_message(self, error: InterpreterError) -> str:
        if error.code == ErrorCode.UNKNOWN_PRIMITIVE:
            return (
                "Your previous response referenced a primitive that does not exist. "
                "Call list_primitives() first and use only names it returns."
            )
        if error.code == ErrorCode.INVALID_JSON_RETRY_FAILED:
            return (
                "Your previous response was not valid JSON. "
                "Return ONLY a valid JSON object matching the Output Contract."
            )
        return f"Previous attempt failed with: {error.message}. Please try again."
