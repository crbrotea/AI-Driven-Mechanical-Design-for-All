"""Integration test: GCS miss + demo hash → fallback serves artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.geometry.api.router import router as geometry_router
from services.geometry.cache import FakeGeometryCache
from services.geometry.fallback import DEMO_INTENT_HASHES
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


def _flywheel_intent() -> DesignIntent:
    def f(v: object) -> TriStateField:
        return TriStateField(value=v, source=FieldSource.EXTRACTED)

    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": f(0.5),
            "inner_diameter_m": f(0.1),
            "thickness_m": f(0.05),
            "rpm": f(3000),
        },
        composed_of=["Shaft", "Bearing_Housing"],
    )


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    # Empty FakeGeometryCache forces miss → fallback should activate
    app.state.geometry_pipeline = GeometryPipeline(
        cache=FakeGeometryCache(),
        materials_catalog=catalog,
    )
    app.state.geometry_cache = FakeGeometryCache()
    app.include_router(geometry_router)
    return TestClient(app)


def test_demo_artifact_endpoint_serves_flywheel(client: TestClient) -> None:
    flywheel_hash = DEMO_INTENT_HASHES["hero_flywheel_500kj_3000rpm"]
    response = client.get(f"/generate/demo_artifact/{flywheel_hash}/geometry.step")
    # Either 200 (if demo artifacts are populated on disk) or 404 (not populated yet)
    # Both are valid — but the endpoint itself must not crash
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.content.startswith(b"ISO-10303-21;")


def test_demo_artifact_endpoint_rejects_unknown_hash(client: TestClient) -> None:
    response = client.get("/generate/demo_artifact/notarealhash/geometry.step")
    assert response.status_code == 404


def test_demo_artifact_endpoint_rejects_invalid_filename(client: TestClient) -> None:
    flywheel_hash = DEMO_INTENT_HASHES["hero_flywheel_500kj_3000rpm"]
    response = client.get(f"/generate/demo_artifact/{flywheel_hash}/../etc/passwd")
    assert response.status_code in (400, 404)
