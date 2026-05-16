"""Fixtures for S3 integration tests. Extends S2 hero intents with operational fields."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.generate_demo_artifacts import HERO_INTENTS
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog
from services.physics.api.router import register_physics_router

_BACKEND = Path(__file__).resolve().parents[3]
_MATERIALS = _BACKEND / "data" / "materials.json"

HERO_OPERATIONAL_FIELDS: dict[str, dict[str, float]] = {
    "Flywheel_Rim": {"rpm": 3000.0},
    "Pelton_Runner": {"head_m": 20.0, "flow_m3_s": 0.5},
    "Hinge_Panel": {"wind_kmh": 100.0},
}


def extend_with_operational(intent: DesignIntent, ops: dict[str, float]) -> DesignIntent:
    new_fields = dict(intent.fields)
    for name, value in ops.items():
        new_fields[name] = TriStateField(value=value, source=FieldSource.EXTRACTED)
    return intent.model_copy(update={"fields": new_fields})


@pytest.fixture(scope="module")
def physics_client() -> Iterable[TestClient]:
    app = FastAPI()
    app.state.catalog = load_catalog(_MATERIALS)
    register_physics_router(app)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def hero_intents() -> dict[str, tuple[str, DesignIntent]]:
    """Map label -> (material_name, extended DesignIntent)."""
    out: dict[str, tuple[str, DesignIntent]] = {}
    for label, material_name, intent in HERO_INTENTS:
        ops = HERO_OPERATIONAL_FIELDS.get(intent.type, {})
        out[label] = (material_name, extend_with_operational(intent, ops))
    return out
