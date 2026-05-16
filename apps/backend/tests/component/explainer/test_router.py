"""Component tests for POST /explain."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.explainer.api.router import register_explainer_router
from services.explainer.cache import ExplainerCache
from services.explainer.generator import Explainer
from services.explainer.prompt import load_system_prompt
from tests.fakes.fake_gemma_text import FakeGemmaTextClient

_BACKEND = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _BACKEND / "prompts"

_VALID_JSON = json.dumps(
    {
        "summary": "ok",
        "risks": [],
        "suggestions": [],
        "analogies": [],
        "facts_used": ["safety_factor"],
    }
)


def _flywheel_intent_dict() -> dict:
    return {
        "type": "Flywheel_Rim",
        "fields": {
            "rpm": {
                "value": 3000.0,
                "source": "extracted",
                "unit": None,
                "original_text": None,
                "reason": None,
            },
            "outer_diameter_m": {
                "value": 0.5,
                "source": "extracted",
                "unit": None,
                "original_text": None,
                "reason": None,
            },
        },
        "composed_of": [],
    }


def _analysis_dict() -> dict:
    return {
        "intent_type": "Flywheel_Rim",
        "material_name": "steel_a36",
        "material_yield_mpa": 250.0,
        "formula": "sigma = rho*omega^2*R^2",
        "stress_max_pa": 1.93e8,
        "displacement_max_m": 4.8e-4,
        "safety_factor": 1.29,
        "verdict": "warn",
        "inputs": {},
        "notes": None,
        "extras": None,
    }


def _make_app(gemma: FakeGemmaTextClient) -> FastAPI:
    app = FastAPI()
    explainer = Explainer(
        gemma=gemma,
        cache=ExplainerCache(),
        system_prompt=load_system_prompt(_PROMPTS_DIR),
    )
    app.state.explainer = explainer
    register_explainer_router(app)
    return app


def _parse_sse_events(text: str) -> list[dict]:
    events: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[len("data:"):].strip())
        elif not line.strip() and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def test_explain_streams_progress_chunk_final() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    r = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    assert r.status_code == 200, r.text
    events = _parse_sse_events(r.text)
    names = [ev["event"] for ev in events]
    assert names[0] == "progress"
    assert "chunk" in names
    assert names[-1] == "final"
    assert events[-1]["data"]["cache_hit"] is False


def test_explain_cache_hit_emits_only_final() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    app = _make_app(fake)
    client = TestClient(app)
    client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    r = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    events = _parse_sse_events(r.text)
    assert [ev["event"] for ev in events] == ["final"]
    assert events[0]["data"]["cache_hit"] is True


def test_explain_invalid_body_returns_422() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    # missing analysis_result
    r = client.post("/explain", json={"intent": {"type": "Flywheel_Rim"}})
    assert r.status_code == 422


def test_explain_malformed_json_twice_emits_error_event() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[["bad"], ["still bad"]])
    client = TestClient(_make_app(fake))
    r = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    events = _parse_sse_events(r.text)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "report_parse_failed"


def test_explain_unknown_intent_type_propagates_parse_path() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    intent = _flywheel_intent_dict()
    intent["type"] = "Unknown_Thing"
    r = client.post("/explain", json={"intent": intent, "analysis_result": _analysis_dict()})
    assert r.status_code == 200
    events = _parse_sse_events(r.text)
    assert events[-1]["event"] == "final"  # FakeGemma returns valid JSON regardless


def test_explain_final_data_contains_facts_used() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    r = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    events = _parse_sse_events(r.text)
    final = events[-1]
    assert final["event"] == "final"
    assert final["data"]["report"]["facts_used"] == ["safety_factor"]


def test_explain_cache_key_is_stable_across_calls() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    app = _make_app(fake)
    client = TestClient(app)
    r1 = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    r2 = client.post(
        "/explain",
        json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()},
    )
    k1 = _parse_sse_events(r1.text)[-1]["data"]["cache_key"]
    k2 = _parse_sse_events(r2.text)[-1]["data"]["cache_key"]
    assert k1 == k2
