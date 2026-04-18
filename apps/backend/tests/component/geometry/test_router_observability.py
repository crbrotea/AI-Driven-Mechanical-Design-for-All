"""Tests for observability wiring in Geometry router."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.geometry.api.router import router as geometry_router
from services.geometry.cache import FakeGeometryCache
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.agent.circuit_breaker import DegradedModeBreaker
from services.interpreter.domain.materials import load_catalog
from services.interpreter.observability.logging import configure_logging
from services.interpreter.observability.metrics import InterpreterMetrics

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture(autouse=True)
def _configure_logging() -> None:
    """Route structlog through stdlib so caplog captures geometry.router logs."""
    configure_logging(level="INFO", json_output=False)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    app.state.geometry_pipeline = GeometryPipeline(
        cache=FakeGeometryCache(), materials_catalog=catalog,
    )
    app.state.geometry_cache = FakeGeometryCache()
    app.state.metrics = InterpreterMetrics()
    app.state.geometry_cache_breaker = DegradedModeBreaker(
        failure_threshold=2, duration_seconds=60,
    )
    app.include_router(geometry_router)
    return TestClient(app)


def test_generate_logs_request_started(
    client: TestClient, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO), client.stream("POST", "/generate", json={
        "intent": {
            "type": "Shaft",
            "fields": {
                "diameter_m": {"value": 0.05, "source": "extracted"},
                "length_m": {"value": 0.5, "source": "extracted"},
            },
            "composed_of": [],
        },
        "material_name": "steel_a36",
    }) as r:
        list(r.iter_bytes())
    logged = [rec.message for rec in caplog.records]
    assert any("generate_request_started" in m for m in logged)


def test_generate_increments_metrics(client: TestClient) -> None:
    with client.stream("POST", "/generate", json={
        "intent": {
            "type": "Shaft",
            "fields": {
                "diameter_m": {"value": 0.05, "source": "extracted"},
                "length_m": {"value": 0.5, "source": "extracted"},
            },
            "composed_of": [],
        },
        "material_name": "steel_a36",
    }) as r:
        list(r.iter_bytes())
    snapshot = client.app.state.metrics.snapshot()
    # We register generate events under interpret.request_count with status=success
    # or add a dedicated bucket — accept either as long as something increments.
    assert any(
        "request_count" in k and sum(v.values()) > 0
        for k, v in snapshot.items() if isinstance(v, dict)
    )
