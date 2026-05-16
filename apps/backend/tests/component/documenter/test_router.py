"""Component tests for POST /document."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.documenter.api.router import register_documenter_router
from services.documenter.cache import DocumenterCache
from services.documenter.pipeline import Documenter
from services.documenter.storage import DocumentStorage
from services.interpreter.domain.materials import load_catalog
from tests.fakes.fake_gcs_client import FakeGcsClient
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher

_BACKEND = Path(__file__).resolve().parents[3]
_MATERIALS = _BACKEND / "data" / "materials.json"


def _intent_dict() -> dict:
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
        },
        "composed_of": [],
    }


def _analysis_dict(material: str = "steel_a36") -> dict:
    return {
        "intent_type": "Flywheel_Rim",
        "material_name": material,
        "material_yield_mpa": 250.0,
        "formula": "sigma = rho*omega^2*R^2",
        "stress_max_pa": 1.937e8,
        "displacement_max_m": 4.84e-4,
        "safety_factor": 1.29,
        "verdict": "warn",
        "inputs": {"angular_velocity_rad_s": 314.159},
        "notes": None,
        "extras": None,
    }


def _narrative_dict() -> dict:
    return {
        "summary": "Near-yield at 3000 rpm.",
        "risks": ["Stress 77 percent of yield."],
        "suggestions": ["Verify with FEA."],
        "analogies": [],
        "facts_used": ["stress_max_mpa", "safety_factor"],
    }


def _artifacts_dict() -> dict:
    return {
        "mass_properties": {
            "volume_m3": 0.012,
            "mass_kg": 95.5,
            "center_of_mass": [0.0, 0.0, 0.025],
            "bbox_m": [-0.25, -0.25, 0.0, 0.25, 0.25, 0.05],
        },
        "step_url": "https://example.com/step",
        "glb_url": "https://example.com/glb",
        "svg_url": "https://example.com/svg",
    }


def _make_app() -> tuple[FastAPI, FakeGcsClient]:
    gcs = FakeGcsClient()
    app = FastAPI()
    app.state.documenter = Documenter(
        storage=DocumentStorage(gcs_client=gcs, bucket_name="b"),
        cache=DocumenterCache(),
        materials_catalog=load_catalog(_MATERIALS),
        svg_fetcher=FakeSvgFetcher(),
    )
    register_documenter_router(app)
    return app, gcs


def test_document_returns_200_with_deliverables() -> None:
    app, _ = _make_app()
    client = TestClient(app)
    r = client.post(
        "/document",
        json={
            "intent": _intent_dict(),
            "analysis_result": _analysis_dict(),
            "natural_report": _narrative_dict(),
            "geometry_artifacts": _artifacts_dict(),
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")
    assert d["step_url"] == "https://example.com/step"
    assert d["cache_hit"] is False
    assert isinstance(d["cache_key"], str)


def test_document_second_call_is_cache_hit() -> None:
    app, _ = _make_app()
    client = TestClient(app)
    payload = {
        "intent": _intent_dict(),
        "analysis_result": _analysis_dict(),
        "natural_report": _narrative_dict(),
        "geometry_artifacts": _artifacts_dict(),
    }
    client.post("/document", json=payload)
    r = client.post("/document", json=payload)
    assert r.json()["cache_hit"] is True


def test_document_invalid_body_returns_422() -> None:
    app, _ = _make_app()
    client = TestClient(app)
    r = client.post(
        "/document",
        json={"intent": _intent_dict()},
    )
    assert r.status_code == 422


def test_document_unknown_material_returns_422() -> None:
    app, _ = _make_app()
    client = TestClient(app)
    r = client.post(
        "/document",
        json={
            "intent": _intent_dict(),
            "analysis_result": _analysis_dict(material="unobtanium"),
            "natural_report": _narrative_dict(),
            "geometry_artifacts": _artifacts_dict(),
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_input"


def test_document_response_echoes_passthrough_urls() -> None:
    app, _ = _make_app()
    client = TestClient(app)
    artifacts = _artifacts_dict()
    artifacts["step_url"] = "https://example.com/echo-step"
    artifacts["glb_url"] = "https://example.com/echo-glb"
    artifacts["svg_url"] = "https://example.com/echo-svg"
    r = client.post(
        "/document",
        json={
            "intent": _intent_dict(),
            "analysis_result": _analysis_dict(),
            "natural_report": _narrative_dict(),
            "geometry_artifacts": artifacts,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["step_url"] == "https://example.com/echo-step"
    assert d["glb_url"] == "https://example.com/echo-glb"
    assert d["svg_url"] == "https://example.com/echo-svg"


def test_document_stores_pdfs_in_documents_prefix() -> None:
    app, gcs = _make_app()
    client = TestClient(app)
    r = client.post(
        "/document",
        json={
            "intent": _intent_dict(),
            "analysis_result": _analysis_dict(),
            "natural_report": _narrative_dict(),
            "geometry_artifacts": _artifacts_dict(),
        },
    )
    key = r.json()["cache_key"]
    assert gcs.stored("b", f"documents/{key}/report.pdf") is not None
    assert gcs.stored("b", f"documents/{key}/drawing.pdf") is not None
