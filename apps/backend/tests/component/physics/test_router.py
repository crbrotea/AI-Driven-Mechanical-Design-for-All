"""Component tests for POST /analyze."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.interpreter.domain.materials import load_catalog
from services.physics.api.router import register_physics_router

_BACKEND = Path(__file__).resolve().parents[3]
_MATERIALS = _BACKEND / "data" / "materials.json"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.state.catalog = load_catalog(_MATERIALS)
    register_physics_router(app)
    return app


def _flywheel_intent(rpm: float = 3000.0) -> dict:
    def _f(v: float) -> dict:
        return {
            "value": v,
            "source": "extracted",
            "unit": None,
            "original_text": None,
            "reason": None,
        }

    return {
        "type": "Flywheel_Rim",
        "fields": {
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(rpm),
        },
        "composed_of": [],
    }


def test_analyze_flywheel_returns_200() -> None:
    client = TestClient(_make_app())
    r = client.post("/analyze", json={"intent": _flywheel_intent(), "material_name": "steel_a36"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent_type"] == "Flywheel_Rim"
    assert body["material_name"] == "steel_a36"
    assert body["verdict"] in {"pass", "warn", "fail"}
    assert body["safety_factor"] > 0
    assert "rho" in body["formula"].lower() or "omega" in body["formula"].lower()


def test_analyze_defaults_to_steel_a36() -> None:
    client = TestClient(_make_app())
    r = client.post("/analyze", json={"intent": _flywheel_intent()})
    assert r.status_code == 200
    assert r.json()["material_name"] == "steel_a36"


def test_analyze_unsupported_intent_type_returns_422() -> None:
    client = TestClient(_make_app())
    intent = _flywheel_intent()
    intent["type"] = "Unknown_Thing"
    r = client.post("/analyze", json={"intent": intent})
    assert r.status_code == 422
    assert r.json()["code"] == "unsupported_intent_type"


def test_analyze_unknown_material_returns_422() -> None:
    client = TestClient(_make_app())
    r = client.post("/analyze", json={"intent": _flywheel_intent(), "material_name": "unobtanium"})
    assert r.status_code == 422
    assert r.json()["code"] == "material_not_found"


def test_analyze_missing_rpm_returns_422() -> None:
    client = TestClient(_make_app())
    intent = _flywheel_intent()
    del intent["fields"]["rpm"]
    r = client.post("/analyze", json={"intent": intent})
    assert r.status_code == 422
    assert r.json()["code"] == "missing_load_parameter"
    assert r.json()["field"] == "rpm"


def test_analyze_invalid_rpm_returns_422() -> None:
    client = TestClient(_make_app())
    r = client.post("/analyze", json={"intent": _flywheel_intent(rpm=-10.0)})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_load_value"


def test_analyze_invalid_body_returns_422() -> None:
    client = TestClient(_make_app())
    r = client.post("/analyze", json={"intent": {"type": "Flywheel_Rim"}})  # missing fields
    assert r.status_code == 422


@pytest.mark.parametrize("intent_type", ["Flywheel_Rim", "Pelton_Runner", "Hinge_Panel"])
def test_analyze_three_heroes_smoke(intent_type: str) -> None:
    client = TestClient(_make_app())
    if intent_type == "Flywheel_Rim":
        intent = _flywheel_intent()
        material = "steel_a36"
    elif intent_type == "Pelton_Runner":

        def _f(v):
            return {
                "value": v,
                "source": "extracted",
                "unit": None,
                "original_text": None,
                "reason": None,
            }

        intent = {
            "type": "Pelton_Runner",
            "fields": {
                "runner_diameter_m": _f(0.8),
                "bucket_count": _f(20),
                "head_m": _f(20.0),
                "flow_m3_s": _f(0.5),
            },
            "composed_of": [],
        }
        material = "stainless_304"
    else:

        def _f(v):
            return {
                "value": v,
                "source": "extracted",
                "unit": None,
                "original_text": None,
                "reason": None,
            }

        intent = {
            "type": "Hinge_Panel",
            "fields": {
                "width_m": _f(1.0),
                "height_m": _f(2.0),
                "thickness_m": _f(0.02),
                "wind_kmh": _f(100.0),
            },
            "composed_of": [],
        }
        material = "bamboo_laminated"
    r = client.post("/analyze", json={"intent": intent, "material_name": material})
    assert r.status_code == 200, r.text
    assert r.json()["intent_type"] == intent_type
