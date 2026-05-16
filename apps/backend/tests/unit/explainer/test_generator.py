"""Explainer generator tests using FakeGemmaTextClient."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.explainer.cache import ExplainerCache
from services.explainer.domain.errors import ExplainErrorCode, ExplainException
from services.explainer.domain.models import NaturalReport
from services.explainer.generator import Explainer
from services.explainer.prompt import load_system_prompt
from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gemma_text import FakeGemmaTextClient

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_SYSTEM = load_system_prompt(_PROMPTS_DIR)


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _result() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.93e8,
        displacement_max_m=4.8e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159},
    )


_VALID_JSON = json.dumps(
    {
        "summary": "Near-yield at 3000 rpm.",
        "risks": ["Stress 193 MPa near 250 MPa yield."],
        "suggestions": ["Verify rim with FEA."],
        "analogies": ["Like a sprinter near top speed."],
        "facts_used": ["stress_max_mpa", "material_yield_mpa", "safety_factor"],
    }
)


async def _collect_events(explainer: Explainer, intent, result):
    out = []
    async for ev in explainer.explain_streaming(intent, result):
        out.append(ev)
    return out


@pytest.mark.asyncio
async def test_generator_emits_progress_chunks_and_final_on_happy_path() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    cache = ExplainerCache()
    explainer = Explainer(gemma=fake, cache=cache, system_prompt=_SYSTEM)

    events = await _collect_events(explainer, _intent(), _result())

    names = [ev.event for ev in events]
    assert names[0] == "progress"
    assert "chunk" in names
    assert names.count("final") == 1
    assert names.count("error") == 0


@pytest.mark.asyncio
async def test_generator_streams_each_chunk_as_chunk_event() -> None:
    pieces = ['{"summary":"a"', ',"risks":[],"suggestions":[],"analogies":[],"facts_used":[]}']
    fake = FakeGemmaTextClient(chunks_per_call=[pieces])
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)

    events = await _collect_events(explainer, _intent(), _result())
    chunk_texts = [ev.data["text"] for ev in events if ev.event == "chunk"]
    assert chunk_texts == pieces


@pytest.mark.asyncio
async def test_generator_final_carries_parsed_report() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)

    events = await _collect_events(explainer, _intent(), _result())
    final = next(ev for ev in events if ev.event == "final")
    report = NaturalReport.model_validate(final.data["report"])
    assert report.summary == "Near-yield at 3000 rpm."
    assert "stress_max_mpa" in report.facts_used
    assert final.data["cache_hit"] is False
    assert isinstance(final.data["cache_key"], str)


@pytest.mark.asyncio
async def test_generator_cache_hit_skips_generation_emits_only_final() -> None:
    cache = ExplainerCache()
    cache.put(
        ExplainerCache.key_for(_intent(), _result()),
        NaturalReport(summary="cached"),
    )
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])  # should not be called
    explainer = Explainer(gemma=fake, cache=cache, system_prompt=_SYSTEM)

    events = await _collect_events(explainer, _intent(), _result())
    assert [ev.event for ev in events] == ["final"]
    assert events[0].data["cache_hit"] is True
    assert fake.call_count == 0


@pytest.mark.asyncio
async def test_generator_retries_once_on_malformed_json() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[["not json"], [_VALID_JSON]])
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)
    events = await _collect_events(explainer, _intent(), _result())
    assert any(ev.event == "final" for ev in events)
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_generator_fails_after_second_malformed_attempt() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[["bad"], ["still bad"]])
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)
    with pytest.raises(ExplainException) as ei:
        await _collect_events(explainer, _intent(), _result())
    assert ei.value.error.code is ExplainErrorCode.REPORT_PARSE_FAILED


@pytest.mark.asyncio
async def test_generator_strips_code_fences() -> None:
    fenced = "```json\n" + _VALID_JSON + "\n```"
    fake = FakeGemmaTextClient(chunks_per_call=[[fenced]])
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)
    events = await _collect_events(explainer, _intent(), _result())
    assert any(ev.event == "final" for ev in events)


@pytest.mark.asyncio
async def test_generator_maps_vertex_timeout_to_gemma_timeout() -> None:
    fake = FakeGemmaTextClient(
        chunks_per_call=[[_VALID_JSON]],
        raise_on_first=VertexTimeout("test"),
    )
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)
    with pytest.raises(ExplainException) as ei:
        await _collect_events(explainer, _intent(), _result())
    assert ei.value.error.code is ExplainErrorCode.GEMMA_TIMEOUT


@pytest.mark.asyncio
async def test_generator_maps_vertex_rate_limited_to_gemma_rate_limited() -> None:
    fake = FakeGemmaTextClient(
        chunks_per_call=[[_VALID_JSON]],
        raise_on_first=VertexRateLimited("quota"),
    )
    explainer = Explainer(gemma=fake, cache=ExplainerCache(), system_prompt=_SYSTEM)
    with pytest.raises(ExplainException) as ei:
        await _collect_events(explainer, _intent(), _result())
    assert ei.value.error.code is ExplainErrorCode.GEMMA_RATE_LIMITED
