"""End-to-end S4 integration over the three hero (intent, AnalysisResult) pairs."""
from __future__ import annotations

import json

import pytest


def parse_sse(text: str) -> list[dict]:
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


@pytest.mark.integration
def test_hero_flywheel_explain_emits_final(
    explain_client, hero_intent_flywheel, hero_result_flywheel
) -> None:
    body = {
        "intent": hero_intent_flywheel.model_dump(),
        "analysis_result": hero_result_flywheel.model_dump(),
    }
    r = explain_client.post("/explain", json=body)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    final = events[-1]
    assert final["event"] == "final"
    assert final["data"]["report"]["summary"]
    assert final["data"]["report"]["facts_used"]


@pytest.mark.integration
def test_hero_hydro_explain_emits_final(
    explain_client, hero_intent_hydro, hero_result_hydro
) -> None:
    body = {
        "intent": hero_intent_hydro.model_dump(),
        "analysis_result": hero_result_hydro.model_dump(),
    }
    r = explain_client.post("/explain", json=body)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    final = events[-1]
    assert final["event"] == "final"
    assert final["data"]["report"]["summary"]


@pytest.mark.integration
def test_hero_shelter_explain_emits_final(
    explain_client, hero_intent_shelter, hero_result_shelter
) -> None:
    body = {
        "intent": hero_intent_shelter.model_dump(),
        "analysis_result": hero_result_shelter.model_dump(),
    }
    r = explain_client.post("/explain", json=body)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    final = events[-1]
    assert final["event"] == "final"
    assert final["data"]["report"]["facts_used"]
