"""Component tests for the agent orchestrator (with mocked Gemma)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
    GemmaToolCall,
)
from services.interpreter.agent.orchestrator import (
    Orchestrator,
    OrchestratorOutput,
)
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.domain.errors import InterpreterException
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry

BACKEND_ROOT = Path(__file__).parent.parent.parent


class _ScriptedGemma(GemmaProtocol):
    """A Gemma stub that replays a predetermined sequence of events."""

    def __init__(self, scripts: list[list[GemmaEvent]]) -> None:
        self._scripts = scripts
        self._call = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
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


async def test_agent_calls_list_primitives_first(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(name="list_primitives", args={})),
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(
                               name="get_primitive_schema",
                               args={"name": "Shaft"})),
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
                ),
            ]
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a 5cm shaft 50cm long")
    assert isinstance(output, OrchestratorOutput)
    assert output.intent.type == "Shaft"
    tool_names = [e.tool_call.name for e in output.events if e.kind == "tool_call"]
    assert tool_names[0] == "list_primitives"


async def test_agent_handles_unknown_primitive_with_retry(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "SuperFlywheel",
                        "fields": {},
                        "composed_of": [],
                    },
                ),
            ],
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Flywheel_Rim",
                        "fields": {
                            "outer_diameter_m": {"value": 0.5, "source": "extracted"},
                            "inner_diameter_m": {"value": 0.1, "source": "extracted"},
                            "thickness_m": {"value": 0.05, "source": "extracted"},
                            "rpm": {"value": 3000, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                ),
            ],
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a flywheel")
    assert output.intent.type == "Flywheel_Rim"
    assert output.retry_count == 1


async def test_agent_stops_after_max_retries(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    bad = GemmaEvent(
        kind="final_json",
        final_json={"type": "StillInvented", "fields": {}, "composed_of": []},
    )
    gemma = _ScriptedGemma(scripts=[[bad], [bad]])  # both attempts fail
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    with pytest.raises(InterpreterException):
        await orch.run(user_prompt="invent something")


async def test_agent_invokes_real_tool_dispatch(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(name="list_primitives", args={})),
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(
                               name="search_materials",
                               args={"criteria": {"category": "metal"}})),
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
                ),
            ]
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a shaft in metal")
    # Tool results should have been captured in events.
    tool_events = [e for e in output.events if e.kind == "tool_result"]
    assert any(e.tool_call.name == "search_materials" for e in tool_events)
    # The tool actually executed and returned metals.
    metal_result = next(
        e.tool_result for e in tool_events if e.tool_call.name == "search_materials"
    )
    assert any(m["category"] == "metal" for m in metal_result)
