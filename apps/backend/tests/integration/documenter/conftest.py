"""Hero (intent, analysis, narrative, geometry) fixtures for S5 integration tests."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.documenter.api.router import register_documenter_router
from services.documenter.cache import DocumenterCache
from services.documenter.pipeline import Documenter
from services.documenter.storage import DocumentStorage
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gcs_client import FakeGcsClient
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher

_BACKEND = Path(__file__).resolve().parents[3]
_MATERIALS = _BACKEND / "data" / "materials.json"


def _f(value: Any) -> TriStateField:
    return TriStateField(value=value, source=FieldSource.EXTRACTED)


# Hero intents carry only GEOMETRIC fields (the ones builders accept).
# Physics-only inputs (rpm, head, flow, wind) belong in `analysis_result.inputs`.
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
            "bucket_count": _f(20),
        },
        composed_of=[],
    ),
    "shelter": DesignIntent(
        type="Hinge_Panel",
        fields={
            "width_m": _f(1.0),
            "height_m": _f(2.0),
            "thickness_m": _f(0.02),
        },
        composed_of=[],
    ),
}

HERO_ANALYSES: dict[str, AnalysisResult] = {
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

HERO_NARRATIVES: dict[str, NaturalReport] = {
    "flywheel": NaturalReport(
        summary="Near-yield at 3000 rpm.",
        risks=["Stress 77% of yield."],
        suggestions=["Verify with FEA."],
        analogies=["Like a sprinter."],
        facts_used=["stress_max_mpa", "safety_factor", "material_yield_mpa"],
    ),
    "hydro": NaturalReport(
        summary="Pelton 0.5 m3/s 20 m head delivers safe torque.",
        risks=["Shaft near material limit."],
        suggestions=["Specify forged 304."],
        analogies=["Like a hand crank with hydraulic boost."],
        facts_used=["safety_factor", "verdict"],
    ),
    "shelter": NaturalReport(
        summary="Bamboo panel handles 100 km/h wind comfortably.",
        risks=[],
        suggestions=["Inspect panel edges yearly."],
        analogies=["Like a sailboat trimming the breeze."],
        facts_used=["safety_factor", "stress_max_mpa"],
    ),
}

_FAKE_BBOX = (-0.25, -0.25, 0.0, 0.25, 0.25, 0.05)


def _artifacts() -> CachedArtifacts:
    return CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=_FAKE_BBOX,
        ),
        step_url="https://example.com/hero/step",
        glb_url="https://example.com/hero/glb",
        svg_url="https://example.com/hero/svg",
    )


@pytest.fixture(scope="module")
def document_client() -> Iterable[TestClient]:
    gcs = FakeGcsClient()
    app = FastAPI()
    app.state.documenter = Documenter(
        storage=DocumentStorage(gcs_client=gcs, bucket_name="b"),
        cache=DocumenterCache(),
        materials_catalog=load_catalog(_MATERIALS),
        svg_fetcher=FakeSvgFetcher(),
    )
    register_documenter_router(app)
    with TestClient(app) as client:
        yield client


def _make_request(hero: str) -> dict:
    return {
        "intent": HERO_INTENTS[hero].model_dump(),
        "analysis_result": HERO_ANALYSES[hero].model_dump(),
        "natural_report": HERO_NARRATIVES[hero].model_dump(),
        "geometry_artifacts": _artifacts().model_dump(),
    }


@pytest.fixture
def hero_flywheel_request() -> dict:
    return _make_request("flywheel")


@pytest.fixture
def hero_hydro_request() -> dict:
    return _make_request("hydro")


@pytest.fixture
def hero_shelter_request() -> dict:
    return _make_request("shelter")
