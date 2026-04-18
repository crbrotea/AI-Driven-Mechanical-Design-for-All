"""Tests for GET /generate/artifacts/{hash}."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.geometry.api.router import router as geometry_router
from services.geometry.cache import FakeGeometryCache
from services.geometry.domain.artifacts import BuiltArtifacts, MassProperties
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.domain.materials import load_catalog

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture
async def client_with_cached_artifact() -> tuple[TestClient, str]:
    app = FastAPI()
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    cache = FakeGeometryCache()
    pipeline = GeometryPipeline(cache=cache, materials_catalog=catalog)
    app.state.geometry_pipeline = pipeline
    app.state.geometry_cache = cache
    app.include_router(geometry_router)

    mass = MassProperties(
        volume_m3=0.01, mass_kg=78.5,
        center_of_mass=(0, 0, 0.025),
        bbox_m=(0, 0, 0, 0.5, 0.5, 0.05),
    )
    await cache.store("abcdef1234567890", BuiltArtifacts(
        step_bytes=b"ISO-10303-21;",
        glb_bytes=b"glTF",
        svg_bytes=b"<svg></svg>",
        mass=mass,
    ))
    return TestClient(app), "abcdef1234567890"


async def test_get_artifacts_returns_cached(client_with_cached_artifact) -> None:
    client, hash_ = client_with_cached_artifact
    response = client.get(f"/generate/artifacts/{hash_}")
    assert response.status_code == 200
    body = response.json()
    assert body["mass_properties"]["mass_kg"] == 78.5
    assert body["artifacts"]["step_url"].startswith("fake://")


async def test_get_unknown_artifact_returns_404() -> None:
    app = FastAPI()
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    cache = FakeGeometryCache()
    pipeline = GeometryPipeline(cache=cache, materials_catalog=catalog)
    app.state.geometry_pipeline = pipeline
    app.state.geometry_cache = cache
    app.include_router(geometry_router)

    client = TestClient(app)
    response = client.get("/generate/artifacts/nonexistent")
    assert response.status_code == 404
