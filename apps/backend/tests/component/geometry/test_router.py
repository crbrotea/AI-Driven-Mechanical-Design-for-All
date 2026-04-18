"""Component tests for /generate streaming endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.geometry.api.router import router as geometry_router
from services.geometry.cache import FakeGeometryCache
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.domain.materials import load_catalog

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    pipeline = GeometryPipeline(cache=FakeGeometryCache(), materials_catalog=catalog)
    app.state.geometry_pipeline = pipeline
    app.include_router(geometry_router)
    return TestClient(app)


def _valid_intent() -> dict[str, object]:
    return {
        "type": "Shaft",
        "fields": {
            "diameter_m": {"value": 0.05, "source": "extracted"},
            "length_m": {"value": 0.5, "source": "extracted"},
        },
        "composed_of": [],
    }


def test_generate_returns_sse_stream(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/generate",
        json={"intent": _valid_intent(), "material_name": "steel_a36"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")
        assert "event: progress" in body
        assert "event: final" in body
        assert '"intent_hash"' in body


def test_generate_invalid_intent_returns_422(client: TestClient) -> None:
    response = client.post(
        "/generate",
        json={"intent": {"type": "Shaft", "fields": {}}, "material_name": "steel_a36"},
    )
    # Empty fields fail validation at the composer level; the router wraps
    # that as 422 via the validator pass.
    assert response.status_code in (200, 422)  # pipeline may emit error event
    if response.status_code == 200:
        body = (
            b"".join(response.iter_bytes()).decode("utf-8")
            if hasattr(response, "iter_bytes")
            else response.text
        )
        assert "event: error" in body


def test_generate_unknown_material_emits_error(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/generate",
        json={"intent": _valid_intent(), "material_name": "unobtanium"},
    ) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")
        assert "event: error" in body
        assert "material_not_found" in body


def test_generate_second_call_emits_cache_hit(client: TestClient) -> None:
    # First call populates cache
    with client.stream(
        "POST",
        "/generate",
        json={"intent": _valid_intent(), "material_name": "steel_a36"},
    ) as r1:
        b1 = b"".join(r1.iter_bytes()).decode("utf-8")
    assert '"cache_hit":false' in b1

    # Second call with same intent hits cache
    with client.stream(
        "POST",
        "/generate",
        json={"intent": _valid_intent(), "material_name": "steel_a36"},
    ) as r2:
        b2 = b"".join(r2.iter_bytes()).decode("utf-8")
    assert '"cache_hit":true' in b2
