"""Component tests for unit normalization in the orchestrator (C1)
and previous_messages pass-through to Gemma (C5).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
)
from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.domain.errors import InterpreterException
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry

BACKEND_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Shared stub infrastructure
# ---------------------------------------------------------------------------


class _ScriptedGemma(GemmaProtocol):
    """Replays a predetermined list of events per call; records received args."""

    def __init__(self, scripts: list[list[GemmaEvent]]) -> None:
        self._scripts = scripts
        self._call = 0
        self.received_previous_messages: list[list[dict] | None] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        self.received_previous_messages.append(previous_messages)
        script = self._scripts[self._call]
        self._call += 1
        for event in script:
            yield event


@pytest.fixture
def tool_registry() -> ToolRegistry:
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    return ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )


@pytest.fixture
def system_prompt() -> str:
    return load_system_prompt(BACKEND_ROOT / "prompts")


def _make_orch(
    gemma: GemmaProtocol, tool_registry: ToolRegistry, system_prompt: str
) -> Orchestrator:
    return Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )


# ---------------------------------------------------------------------------
# C1 — Unit normalizer wired into the pipeline
# ---------------------------------------------------------------------------


async def test_normalizer_converts_inches_to_meters(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """'2 inches' in the Gemma JSON must arrive as ~0.0508 m in the intent."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": "2 inches", "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    output = await orch.run(user_prompt="a 2-inch diameter shaft 50cm long")

    diameter_field = output.intent.fields["diameter_m"]
    assert isinstance(diameter_field.value, float)
    assert abs(diameter_field.value - 0.0508) < 1e-6
    assert diameter_field.original == "2 inches"


async def test_normalizer_converts_centimeters_to_meters(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """'5 cm' must normalize to 0.05 m."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": "5 cm", "source": "extracted"},
                            "length_m": {"value": "50 cm", "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    output = await orch.run(user_prompt="a 5cm shaft 50cm long")

    diameter = output.intent.fields["diameter_m"]
    assert abs(diameter.value - 0.05) < 1e-9
    assert diameter.original == "5 cm"

    length = output.intent.fields["length_m"]
    assert abs(length.value - 0.50) < 1e-9
    assert length.original == "50 cm"


async def test_normalizer_leaves_numeric_values_unchanged(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """Values that are already numeric must not be touched."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": 0.05, "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    output = await orch.run(user_prompt="a 5cm shaft 50cm long")

    diameter = output.intent.fields["diameter_m"]
    assert diameter.value == 0.05
    assert diameter.original is None  # untouched — no original set


async def test_normalizer_propagates_unit_parse_failed(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """An unrecognizable unit string must raise InterpreterException(UNIT_PARSE_FAILED)."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {
                                "value": "gibberish_unit_xyz",
                                "source": "extracted",
                            },
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    from services.interpreter.domain.errors import ErrorCode

    with pytest.raises(InterpreterException) as exc_info:
        await orch.run(user_prompt="bad unit prompt")
    assert exc_info.value.error.code == ErrorCode.UNIT_PARSE_FAILED


# ---------------------------------------------------------------------------
# C5 — previous_messages flows through orchestrator → Gemma
# ---------------------------------------------------------------------------


async def test_previous_messages_passed_to_gemma(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """previous_messages given to run() must be forwarded to gemma.generate()."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": 0.05, "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    prev = [
        {"role": "user", "content": "first turn"},
        {"role": "assistant", "content": '{"type":"Shaft","fields":{}}'},
    ]
    await orch.run(user_prompt="refine it", previous_messages=prev)

    assert gemma.received_previous_messages[0] == prev


async def test_no_previous_messages_passes_none_to_gemma(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    """When previous_messages is omitted, Gemma must receive None."""
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": 0.05, "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                )
            ]
        ]
    )
    orch = _make_orch(gemma, tool_registry, system_prompt)
    await orch.run(user_prompt="a shaft")

    assert gemma.received_previous_messages[0] is None
