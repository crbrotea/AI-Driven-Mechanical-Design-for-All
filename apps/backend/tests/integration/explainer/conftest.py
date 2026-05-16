"""Hero (DesignIntent, AnalysisResult) fixtures for S4 integration tests."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.explainer.api.router import register_explainer_router
from services.explainer.cache import ExplainerCache
from services.explainer.generator import Explainer
from services.explainer.prompt import load_system_prompt
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gemma_text import FakeGemmaTextClient

_BACKEND = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _BACKEND / "prompts"


def _f(value: float, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


HERO_INTENTS: dict[str, DesignIntent] = {
    "flywheel": DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(3000.0),
        },
        composed_of=[],
    ),
    "hydro": DesignIntent(
        type="Pelton_Runner",
        fields={
            "runner_diameter_m": _f(0.8),
            "bucket_count": _f(20.0),
            "head_m": _f(20.0),
            "flow_m3_s": _f(0.5),
        },
        composed_of=[],
    ),
    "shelter": DesignIntent(
        type="Hinge_Panel",
        fields={
            "width_m": _f(1.0),
            "height_m": _f(2.0),
            "thickness_m": _f(0.02),
            "wind_kmh": _f(100.0),
        },
        composed_of=[],
    ),
}


HERO_RESULTS: dict[str, AnalysisResult] = {
    "flywheel": AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159, "outer_diameter_m": 0.5},
    ),
    "hydro": AnalysisResult(
        intent_type="Pelton_Runner",
        material_name="stainless_304",
        material_yield_mpa=215.0,
        formula="tau = 16T/(pi*d^3)",
        stress_max_pa=8.0e7,
        displacement_max_m=2.5e-4,
        safety_factor=1.55,
        verdict=Verdict.WARN,
        inputs={"head_m": 20.0, "flow_m3_s": 0.5},
    ),
    "shelter": AnalysisResult(
        intent_type="Hinge_Panel",
        material_name="bamboo_laminated",
        material_yield_mpa=60.0,
        formula="sigma = 6*P*L^2/t^2",
        stress_max_pa=2.0e7,
        displacement_max_m=1.5e-3,
        safety_factor=3.0,
        verdict=Verdict.PASS,
        inputs={"wind_speed_m_s": 27.78, "pressure_pa": 378.5},
    ),
}


def _valid_report_json(summary: str, facts_used: list[str]) -> str:
    return json.dumps(
        {
            "summary": summary,
            "risks": ["risk"],
            "suggestions": ["suggestion"],
            "analogies": ["analogy"],
            "facts_used": facts_used,
        }
    )


@pytest.fixture(scope="module")
def explain_client() -> Iterable[TestClient]:
    fake = FakeGemmaTextClient(
        chunks_per_call=[[_valid_report_json("hero narrative", ["safety_factor", "verdict"])]] * 10
    )
    app = FastAPI()
    explainer = Explainer(
        gemma=fake,
        cache=ExplainerCache(),
        system_prompt=load_system_prompt(_PROMPTS_DIR),
    )
    app.state.explainer = explainer
    register_explainer_router(app)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def hero_intent_flywheel() -> DesignIntent:
    return HERO_INTENTS["flywheel"]


@pytest.fixture
def hero_result_flywheel() -> AnalysisResult:
    return HERO_RESULTS["flywheel"]


@pytest.fixture
def hero_intent_hydro() -> DesignIntent:
    return HERO_INTENTS["hydro"]


@pytest.fixture
def hero_result_hydro() -> AnalysisResult:
    return HERO_RESULTS["hydro"]


@pytest.fixture
def hero_intent_shelter() -> DesignIntent:
    return HERO_INTENTS["shelter"]


@pytest.fixture
def hero_result_shelter() -> AnalysisResult:
    return HERO_RESULTS["shelter"]
