"""Integration tests hitting real Vertex AI. Requires GCP credentials.

Run with: uv run pytest tests/integration/ -m vertex
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.agent.vertex_gemma import VertexGemmaClient
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry

BACKEND_ROOT = Path(__file__).parent.parent.parent


pytestmark = pytest.mark.vertex


@pytest.fixture
def orchestrator() -> Orchestrator:
    project_id = os.environ["GCP_PROJECT_ID"]
    region = os.environ.get("GCP_REGION", "us-central1")
    model_name = os.environ.get("VERTEX_AI_ENDPOINT", "gemma-4-instruct")

    gemma = VertexGemmaClient(
        project_id=project_id,
        region=region,
        model_name=model_name,
    )
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    tools = ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )
    system_prompt = load_system_prompt(BACKEND_ROOT / "prompts")
    return Orchestrator(
        gemma=gemma,
        tools=tools,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )


async def test_real_flywheel_extraction_es(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Diseña un volante de inercia para 500 kJ a 3000 RPM"
    )
    assert output.intent.type == "Flywheel_Rim"


async def test_real_hydro_extraction_en(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Design a hydroelectric generator for 5 m³/s flow at 20m head"
    )
    assert output.intent.type == "Pelton_Runner"


async def test_real_shelter_extraction_es(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Un refugio plegable para 4 personas, viento 100 km/h"
    )
    assert output.intent.type == "Hinge_Panel"


async def test_real_bilingual_mixed_units(orchestrator: Orchestrator) -> None:
    # Tests imperial parsing path.
    output = await orchestrator.run(
        user_prompt="A shaft 2 inches in diameter and 18 inches long"
    )
    assert output.intent.type == "Shaft"


async def test_real_missing_field_marked_missing(
    orchestrator: Orchestrator,
) -> None:
    output = await orchestrator.run(user_prompt="a flywheel for my project")
    assert output.intent.has_missing_fields()
