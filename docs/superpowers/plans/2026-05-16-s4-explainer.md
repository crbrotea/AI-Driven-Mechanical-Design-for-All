# S4 Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the S4 Explainer subsystem — a streaming `POST /explain` endpoint that takes a `DesignIntent` + `AnalysisResult`, asks Gemma 4 (grounded, temperature 0.3) to produce a `NaturalReport`, validates it as JSON via Pydantic, and emits the result through Server-Sent Events.

**Architecture:** Four-layer mirror of S3 — HTTP → prompt layer (facts + system prompt) → generation (Vertex Gemma streaming + JSON parse + 1 retry) → in-memory cache. Reuses S1's `VertexGemmaClient` via one new method `generate_text_streaming`. Stateless except for the per-process cache.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, structlog, google-cloud-aiplatform / vertexai, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-16-s4-explainer-design.md`

---

## Pre-flight

Run all commands from `apps/backend/` unless stated otherwise. Use `uv run` for every Python command. The repo branch is `master` (user-consented direct commits, conventional-commit style, no `Co-Authored-By`, no `--no-verify`, never `uv build`). Existing uncommitted edits in `services/geometry/primitives/*.py` from S2 close-out and `apps/frontend/next-env.d.ts` are unrelated to S4 and must NOT be staged.

ASCII-only in code strings: replace any Greek (`σ ρ ω τ π`) with ASCII (`sigma rho omega tau pi`) in production code and tests. Ruff RUF001/RUF002 catches them; the executor note in `docs/superpowers/plans/2026-05-16-s3-physics.md` documents the convention adopted in the codebase.

---

## File Structure

**Created**:

```
apps/backend/services/explainer/
├── __init__.py                                # empty package marker
├── README.md
├── domain/
│   ├── __init__.py
│   ├── errors.py                              # ExplainErrorCode, ExplainError, ExplainException
│   └── models.py                              # NaturalReport, ExplainRequest
├── facts.py                                   # build_facts(intent, result)
├── prompt.py                                  # load_system_prompt, build_user_prompt, build_strict_retry_prompt
├── cache.py                                   # ExplainerCache
├── generator.py                               # Explainer + ExplainEvent + _strip_codefence
└── api/
    ├── __init__.py
    └── router.py                              # POST /explain SSE + register_explainer_router

apps/backend/prompts/
└── explainer_system.md                        # system prompt verbatim

apps/backend/tests/fakes/
├── __init__.py                                # empty
└── fake_gemma_text.py                         # FakeGemmaTextClient

apps/backend/tests/unit/explainer/
├── __init__.py
├── test_models.py
├── test_errors.py
├── test_facts.py
├── test_prompt.py
├── test_cache.py
└── test_generator.py

apps/backend/tests/component/explainer/
├── __init__.py
└── test_router.py

apps/backend/tests/integration/explainer/
├── __init__.py
├── conftest.py                                # hero (intent, AnalysisResult) fixtures
└── test_hero_explanations.py
```

**Modified**:

- `apps/backend/services/interpreter/agent/gemma_client.py` — add `VertexTimeout` and `VertexRateLimited` sentinel exceptions at end of file
- `apps/backend/services/interpreter/agent/vertex_gemma.py` — add `generate_text_streaming` method on `VertexGemmaClient` (~30 LOC)
- `apps/backend/main.py` — instantiate a second `VertexGemmaClient` with `temperature=0.3`, build `Explainer`, call `register_explainer_router(app)`

---

## Task 1: Domain — NaturalReport + ExplainRequest

**Files:**
- Create: `apps/backend/services/explainer/__init__.py` (empty)
- Create: `apps/backend/services/explainer/domain/__init__.py` (empty)
- Create: `apps/backend/services/explainer/domain/models.py`
- Create: `apps/backend/tests/unit/explainer/__init__.py` (empty)
- Create: `apps/backend/tests/unit/explainer/test_models.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_models.py`

```python
"""NaturalReport + ExplainRequest tests."""
from __future__ import annotations

import json

from services.explainer.domain.models import ExplainRequest, NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


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
        stress_max_pa=1.0e8,
        displacement_max_m=1.0e-3,
        safety_factor=2.5,
        verdict=Verdict.PASS,
        inputs={},
    )


def test_natural_report_roundtrip() -> None:
    report = NaturalReport(
        summary="A solid design at 3000 rpm.",
        risks=["Stress near 40% of yield."],
        suggestions=["Consider increasing radius."],
        analogies=["Like a wheel that never tires."],
        facts_used=["safety_factor", "stress_max_mpa"],
    )
    parsed = NaturalReport.model_validate_json(report.model_dump_json())
    assert parsed.summary == report.summary
    assert parsed.facts_used == ["safety_factor", "stress_max_mpa"]


def test_natural_report_defaults() -> None:
    report = NaturalReport(summary="x")
    assert report.risks == []
    assert report.suggestions == []
    assert report.analogies == []
    assert report.facts_used == []


def test_explain_request_accepts_intent_and_analysis() -> None:
    req = ExplainRequest(intent=_intent(), analysis_result=_result(), session_id="abc")
    assert req.intent.type == "Flywheel_Rim"
    assert req.analysis_result.verdict is Verdict.PASS
    assert req.session_id == "abc"


def test_explain_request_session_id_optional() -> None:
    req = ExplainRequest(intent=_intent(), analysis_result=_result())
    assert req.session_id is None
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_models.py -v`
Expected: `ModuleNotFoundError: No module named 'services.explainer'`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/domain/models.py`

```python
"""Domain models for S4 Explainer."""
from __future__ import annotations

from pydantic import BaseModel, Field

from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class NaturalReport(BaseModel):
    """Structured natural-language report. Output of S4."""

    summary: str = Field(..., description="<=80 word plain-English summary")
    risks: list[str] = Field(default_factory=list, description="1-4 short bullets")
    suggestions: list[str] = Field(default_factory=list, description="1-4 actionable bullets")
    analogies: list[str] = Field(default_factory=list, description="1-2 lay analogies")
    facts_used: list[str] = Field(default_factory=list, description="exact FACTS labels cited")


class ExplainRequest(BaseModel):
    """Request body for POST /explain."""

    intent: DesignIntent
    analysis_result: AnalysisResult
    session_id: str | None = None
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/explainer/__init__.py \
        apps/backend/services/explainer/domain/__init__.py \
        apps/backend/services/explainer/domain/models.py \
        apps/backend/tests/unit/explainer/__init__.py \
        apps/backend/tests/unit/explainer/test_models.py
git commit -m "feat(explainer): add NaturalReport and ExplainRequest models"
```

---

## Task 2: Domain — Error taxonomy

**Files:**
- Create: `apps/backend/services/explainer/domain/errors.py`
- Create: `apps/backend/tests/unit/explainer/test_errors.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_errors.py`

```python
"""Explainer error taxonomy tests."""
from __future__ import annotations

import json

import pytest

from services.explainer.domain.errors import (
    ExplainError,
    ExplainErrorCode,
    ExplainException,
)


def test_codes_stable() -> None:
    assert ExplainErrorCode.INVALID_INPUT.value == "invalid_input"
    assert ExplainErrorCode.GEMMA_TIMEOUT.value == "gemma_timeout"
    assert ExplainErrorCode.GEMMA_RATE_LIMITED.value == "gemma_rate_limited"
    assert ExplainErrorCode.GEMMA_FAILED.value == "gemma_failed"
    assert ExplainErrorCode.REPORT_PARSE_FAILED.value == "report_parse_failed"
    assert ExplainErrorCode.REPORT_SCHEMA_INVALID.value == "report_schema_invalid"
    assert ExplainErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_http_status_mapping() -> None:
    assert ExplainError(code=ExplainErrorCode.INVALID_INPUT, message="x").http_status == 422
    assert ExplainError(code=ExplainErrorCode.GEMMA_TIMEOUT, message="x").http_status == 504
    assert ExplainError(code=ExplainErrorCode.GEMMA_RATE_LIMITED, message="x").http_status == 429
    assert ExplainError(code=ExplainErrorCode.REPORT_PARSE_FAILED, message="x").http_status == 500
    assert ExplainError(code=ExplainErrorCode.INTERNAL_ERROR, message="x").http_status == 500


def test_serializes() -> None:
    err = ExplainError(
        code=ExplainErrorCode.GEMMA_TIMEOUT,
        message="timed out",
        retry_after=5,
    )
    payload = json.loads(err.model_dump_json())
    assert payload["code"] == "gemma_timeout"
    assert payload["retry_after"] == 5


def test_raise_as_wraps_in_exception() -> None:
    err = ExplainError(code=ExplainErrorCode.REPORT_PARSE_FAILED, message="bad json")
    with pytest.raises(ExplainException) as ei:
        err.raise_as()
    assert ei.value.error.code is ExplainErrorCode.REPORT_PARSE_FAILED
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_errors.py -v`
Expected: ImportError on `services.explainer.domain.errors`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/domain/errors.py`

```python
"""Structured error taxonomy for S4 Explainer."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ExplainErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    GEMMA_TIMEOUT = "gemma_timeout"
    GEMMA_RATE_LIMITED = "gemma_rate_limited"
    GEMMA_FAILED = "gemma_failed"
    REPORT_PARSE_FAILED = "report_parse_failed"
    REPORT_SCHEMA_INVALID = "report_schema_invalid"
    INTERNAL_ERROR = "internal_error"


_STATUS_MAP: dict[ExplainErrorCode, int] = {
    ExplainErrorCode.INVALID_INPUT: 422,
    ExplainErrorCode.GEMMA_TIMEOUT: 504,
    ExplainErrorCode.GEMMA_RATE_LIMITED: 429,
    ExplainErrorCode.GEMMA_FAILED: 502,
    ExplainErrorCode.REPORT_PARSE_FAILED: 500,
    ExplainErrorCode.REPORT_SCHEMA_INVALID: 500,
    ExplainErrorCode.INTERNAL_ERROR: 500,
}


class ExplainError(BaseModel):
    code: ExplainErrorCode
    message: str
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return _STATUS_MAP.get(self.code, 500)

    def raise_as(self) -> None:
        raise ExplainException(self)


class ExplainException(RuntimeError):  # noqa: N818 -- intentional distinction from ExplainError model
    """Raised by generator and router internals; carries an ExplainError payload."""

    def __init__(self, error: ExplainError) -> None:
        super().__init__(error.message)
        self.error = error
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_errors.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/explainer/domain/errors.py \
        apps/backend/tests/unit/explainer/test_errors.py
git commit -m "feat(explainer): add explainer error taxonomy"
```

---

## Task 3: Vertex sentinel exceptions

**Files:**
- Modify: `apps/backend/services/interpreter/agent/gemma_client.py` (append at end)
- Create: `apps/backend/tests/unit/explainer/test_vertex_sentinels.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_vertex_sentinels.py`

```python
"""Vertex sentinel exceptions used by the explainer to map Vertex failures."""
from __future__ import annotations

import pytest

from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout


def test_vertex_timeout_is_runtime_error() -> None:
    err = VertexTimeout("Vertex took too long")
    assert isinstance(err, RuntimeError)
    assert str(err) == "Vertex took too long"


def test_vertex_rate_limited_is_runtime_error() -> None:
    err = VertexRateLimited("quota exhausted")
    assert isinstance(err, RuntimeError)
    assert str(err) == "quota exhausted"


def test_sentinels_are_distinct() -> None:
    assert VertexTimeout is not VertexRateLimited
    assert not issubclass(VertexTimeout, VertexRateLimited)
    assert not issubclass(VertexRateLimited, VertexTimeout)
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_vertex_sentinels.py -v`
Expected: `ImportError: cannot import name 'VertexTimeout' from 'services.interpreter.agent.gemma_client'`.

- [ ] **Step 3: Append to `apps/backend/services/interpreter/agent/gemma_client.py`**

```python


class VertexTimeout(RuntimeError):
    """Raised by Vertex client wrappers when a request exceeds the per-call timeout."""


class VertexRateLimited(RuntimeError):
    """Raised by Vertex client wrappers when the API returns 429 / quota exhausted."""
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_vertex_sentinels.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/agent/gemma_client.py \
        apps/backend/tests/unit/explainer/test_vertex_sentinels.py
git commit -m "feat(interpreter): add VertexTimeout and VertexRateLimited sentinels"
```

---

## Task 4: VertexGemmaClient.generate_text_streaming

**Files:**
- Modify: `apps/backend/services/interpreter/agent/vertex_gemma.py` (append method on class)
- Create: `apps/backend/tests/fakes/__init__.py` (empty)
- Create: `apps/backend/tests/fakes/fake_gemma_text.py`

This task adds the production method but also delivers the `FakeGemmaTextClient` test double that subsequent tests need. Both ship together because the fake's interface is the contract.

- [ ] **Step 1: Write the FakeGemmaTextClient** — `apps/backend/tests/fakes/fake_gemma_text.py`

```python
"""Deterministic in-process stand-in for VertexGemmaClient.generate_text_streaming.

Each constructor accepts a list of "calls", where each call is a list of text
chunks the fake will yield. Use this to script malformed/valid JSON sequences
and exception injection for retry tests.
"""
from __future__ import annotations

from collections.abc import AsyncIterator


class FakeGemmaTextClient:
    def __init__(
        self,
        chunks_per_call: list[list[str]],
        raise_on_first: Exception | None = None,
    ) -> None:
        if not chunks_per_call:
            raise ValueError("chunks_per_call must be non-empty")
        self._chunks_per_call = chunks_per_call
        self._call_count = 0
        self._raise_first = raise_on_first

    @property
    def call_count(self) -> int:
        return self._call_count

    async def generate_text_streaming(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]:
        del system_prompt, user_prompt  # not used by fake, signature must match real client
        self._call_count += 1
        if self._call_count == 1 and self._raise_first is not None:
            raise self._raise_first
        idx = min(self._call_count - 1, len(self._chunks_per_call) - 1)
        for chunk in self._chunks_per_call[idx]:
            yield chunk
```

- [ ] **Step 2: Read the existing `vertex_gemma.py` to know where to add the method**

Run: `grep -n "class VertexGemmaClient\|async def generate" apps/backend/services/interpreter/agent/vertex_gemma.py`

Expect a class around lines 26-30 with an existing `async def generate(...)` method. Add the new method AFTER the existing `generate` method, inside the class. The class already imports `asyncio`, `AsyncIterator`, `Any`, `google_exc`, and the `vertexai` types it needs; you may need to add `from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout` at the import block (top of file).

- [ ] **Step 3: Add the import at the top of `apps/backend/services/interpreter/agent/vertex_gemma.py`**

Find the existing line `from services.interpreter.agent.gemma_client import (` and add `VertexRateLimited` and `VertexTimeout` to the import list, e.g.:

```python
from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaToolCall,
    VertexRateLimited,
    VertexTimeout,
)
```

- [ ] **Step 4: Append the new method inside `class VertexGemmaClient` in `apps/backend/services/interpreter/agent/vertex_gemma.py`**

```python
    async def generate_text_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        """Plain text streaming, no tools. Yields raw text chunks.

        Uses response_mime_type='application/json' so Gemma produces JSON
        directly. The caller is responsible for parsing the accumulated text.
        """
        try:
            stream = await asyncio.wait_for(
                self._model.generate_content_async(
                    [system_prompt, user_prompt],
                    generation_config={
                        "temperature": self._temperature,
                        "max_output_tokens": self._max_output_tokens,
                        "response_mime_type": "application/json",
                    },
                    stream=True,
                ),
                timeout=self._timeout_s,
            )
        except TimeoutError as exc:
            raise VertexTimeout("Vertex AI text streaming timed out") from exc
        except google_exc.ResourceExhausted as exc:
            raise VertexRateLimited(f"Vertex AI quota exhausted: {exc}") from exc

        async for chunk in stream:
            for candidate in chunk.candidates:
                for part in candidate.content.parts:
                    text = getattr(part, "text", "")
                    if text:
                        yield text
```

- [ ] **Step 5: Verify ruff + mypy stay clean**

Run:
```bash
uv run ruff check services/interpreter/agent/vertex_gemma.py services/interpreter/agent/gemma_client.py
uv run mypy services/interpreter/agent/vertex_gemma.py services/interpreter/agent/gemma_client.py
```
Expected: `All checks passed!` and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/interpreter/agent/vertex_gemma.py \
        apps/backend/tests/fakes/__init__.py \
        apps/backend/tests/fakes/fake_gemma_text.py
git commit -m "feat(interpreter): add generate_text_streaming method on VertexGemmaClient"
```

The fake will get its own tests indirectly through generator tests in Task 8. No separate test commit for the fake itself.

---

## Task 5: Facts table builder

**Files:**
- Create: `apps/backend/services/explainer/facts.py`
- Create: `apps/backend/tests/unit/explainer/test_facts.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_facts.py`

```python
"""build_facts tests."""
from __future__ import annotations

from services.explainer.facts import build_facts
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent_flywheel() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def _result_flywheel() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=193.7e6,
        displacement_max_m=4.8e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159, "outer_diameter_m": 0.5},
    )


def test_facts_includes_all_core_outputs() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert facts["intent_type"] == "Flywheel_Rim"
    assert facts["material_name"] == "steel_a36"
    assert facts["material_yield_mpa"] == "250.0 MPa"
    assert facts["stress_max_mpa"] == "193.70 MPa"
    assert facts["displacement_max_mm"] == "0.480 mm"
    assert facts["safety_factor"] == "1.29"
    assert facts["verdict"] == "WARN"
    assert facts["formula"] == "sigma = rho*omega^2*R^2"


def test_facts_includes_solver_inputs_with_prefix() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert "input.angular_velocity_rad_s" in facts
    assert facts["input.angular_velocity_rad_s"] == "314.159"


def test_facts_includes_intent_fields_with_prefix() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert facts["intent.outer_diameter_m"] == "0.5"
    assert facts["intent.inner_diameter_m"] == "0.1"
    assert facts["intent.rpm"] == "3000.0"


def test_facts_skips_intent_field_with_none_value() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "head_m": TriStateField(value=None, source=FieldSource.MISSING),
        },
        composed_of=[],
    )
    facts = build_facts(intent, _result_flywheel())
    assert "intent.outer_diameter_m" in facts
    assert "intent.head_m" not in facts


def test_facts_verdict_is_uppercased() -> None:
    result = _result_flywheel()
    facts = build_facts(_intent_flywheel(), result)
    assert facts["verdict"] == result.verdict.value.upper()
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_facts.py -v`
Expected: ImportError on `services.explainer.facts`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/facts.py`

```python
"""Build the FACTS table fed to Gemma for grounded narration."""
from __future__ import annotations

from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


def build_facts(intent: DesignIntent, result: AnalysisResult) -> dict[str, str]:
    """Return a flat dict {label: formatted_value} fed to Gemma.

    Every number Gemma is allowed to cite MUST be present here. If a value
    is not here, Gemma must NOT invent it.
    """
    facts: dict[str, str] = {
        "intent_type": intent.type,
        "material_name": result.material_name,
        "material_yield_mpa": f"{result.material_yield_mpa:.1f} MPa",
        "formula": result.formula,
        "stress_max_mpa": f"{result.stress_max_pa / 1e6:.2f} MPa",
        "displacement_max_mm": f"{result.displacement_max_m * 1e3:.3f} mm",
        "safety_factor": f"{result.safety_factor:.2f}",
        "verdict": result.verdict.value.upper(),
    }
    for k, v in result.inputs.items():
        facts[f"input.{k}"] = f"{v:.3f}"
    for name, field in intent.fields.items():
        if field.value is not None:
            facts[f"intent.{name}"] = f"{field.value}"
    return facts
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_facts.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/explainer/facts.py \
        apps/backend/tests/unit/explainer/test_facts.py
git commit -m "feat(explainer): add FACTS table builder for Gemma grounding"
```

---

## Task 6: Prompt loader + system prompt asset

**Files:**
- Create: `apps/backend/prompts/explainer_system.md`
- Create: `apps/backend/services/explainer/prompt.py`
- Create: `apps/backend/tests/unit/explainer/test_prompt.py`

- [ ] **Step 1: Write the system prompt** — `apps/backend/prompts/explainer_system.md`

```markdown
You are a mechanical engineering explainer for a non-expert audience. You
receive a FACTS table with the actual numerical results from a structural
analysis. Your job: produce a JSON report that narrates these results
clearly to someone who doesn't read formulas.

STRICT RULES:

1. Use ONLY values that appear in the FACTS table. NEVER invent numbers.
2. If you want to mention a value that is not in the FACTS table, write
   "(not available)" instead.
3. Output MUST be valid JSON matching this schema (no surrounding prose,
   no code fences):
   {
     "summary":    "<<=80 word plain-English summary>",
     "risks":      ["<short bullet>", ...],
     "suggestions":["<short bullet>", ...],
     "analogies":  ["<short bullet>", ...],
     "facts_used": ["<label>", ...]
   }
4. Every number you cite in summary/risks/suggestions/analogies MUST have
   its label in facts_used.
5. Match the verdict tone:
   - PASS: confident, positive, brief.
   - WARN: cautious, "near limit", suggest verification.
   - FAIL: serious; explain why; suggest one concrete fix.
6. Keep the language plain. Avoid jargon unless you also define it.
```

- [ ] **Step 2: Write the failing test** — `apps/backend/tests/unit/explainer/test_prompt.py`

```python
"""Prompt loader + builder tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.explainer.prompt import (
    build_strict_retry_prompt,
    build_user_prompt,
    load_system_prompt,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def test_load_system_prompt_carries_anti_fabrication_rule() -> None:
    text = load_system_prompt(_PROMPTS_DIR)
    assert "NEVER invent" in text
    assert "FACTS table" in text
    assert "facts_used" in text


def test_load_system_prompt_describes_schema() -> None:
    text = load_system_prompt(_PROMPTS_DIR)
    assert "summary" in text
    assert "risks" in text
    assert "suggestions" in text
    assert "analogies" in text


def test_build_user_prompt_embeds_facts_table() -> None:
    facts = {"stress_max_mpa": "193.70 MPa", "safety_factor": "1.29"}
    rendered = build_user_prompt(facts)
    assert "FACTS:" in rendered
    assert "stress_max_mpa = 193.70 MPa" in rendered
    assert "safety_factor = 1.29" in rendered
    assert "Produce the JSON report now." in rendered


def test_build_strict_retry_prompt_appends_strict_instruction() -> None:
    facts = {"verdict": "WARN"}
    base = build_user_prompt(facts)
    strict = build_strict_retry_prompt(facts)
    assert strict.startswith(base)
    assert "Output ONLY valid JSON" in strict


def test_load_system_prompt_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_system_prompt(Path("/no/such/dir"))
```

- [ ] **Step 3: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_prompt.py -v`
Expected: ImportError on `services.explainer.prompt`.

- [ ] **Step 4: Write production code** — `apps/backend/services/explainer/prompt.py`

```python
"""System prompt loader + user prompt renderer for the explainer."""
from __future__ import annotations

from pathlib import Path

_SYSTEM_PROMPT_FILENAME = "explainer_system.md"


def load_system_prompt(prompts_dir: Path) -> str:
    """Load the system prompt from `<prompts_dir>/explainer_system.md`."""
    return (prompts_dir / _SYSTEM_PROMPT_FILENAME).read_text(encoding="utf-8")


def build_user_prompt(facts: dict[str, str]) -> str:
    facts_block = "\n".join(f"  {k} = {v}" for k, v in facts.items())
    return f"FACTS:\n{facts_block}\n\nProduce the JSON report now."


def build_strict_retry_prompt(facts: dict[str, str]) -> str:
    base = build_user_prompt(facts)
    return base + "\n\nIMPORTANT: Output ONLY valid JSON. No prose, no code fences."
```

- [ ] **Step 5: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_prompt.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/prompts/explainer_system.md \
        apps/backend/services/explainer/prompt.py \
        apps/backend/tests/unit/explainer/test_prompt.py
git commit -m "feat(explainer): add system prompt asset and prompt builders"
```

---

## Task 7: Cache

**Files:**
- Create: `apps/backend/services/explainer/cache.py`
- Create: `apps/backend/tests/unit/explainer/test_cache.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_cache.py`

```python
"""ExplainerCache tests."""
from __future__ import annotations

import math

from services.explainer.cache import ExplainerCache
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent(rpm: float = 3000.0) -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=rpm, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _result(sf: float = 1.29, stress_pa: float = 1.93e8) -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=stress_pa,
        displacement_max_m=4.8e-4,
        safety_factor=sf,
        verdict=Verdict.WARN if sf < 2.0 else Verdict.PASS,
        inputs={},
    )


def test_get_returns_none_on_miss() -> None:
    cache = ExplainerCache()
    assert cache.get("nonexistent") is None


def test_put_then_get_roundtrip() -> None:
    cache = ExplainerCache()
    report = NaturalReport(summary="ok")
    cache.put("k1", report)
    assert cache.get("k1") is report


def test_key_is_deterministic() -> None:
    intent = _intent()
    result = _result()
    k1 = ExplainerCache.key_for(intent, result)
    k2 = ExplainerCache.key_for(intent, result)
    assert k1 == k2
    assert len(k1) == 16


def test_key_changes_when_safety_factor_changes() -> None:
    intent = _intent()
    k1 = ExplainerCache.key_for(intent, _result(sf=1.29))
    k2 = ExplainerCache.key_for(intent, _result(sf=2.5))
    assert k1 != k2


def test_key_changes_when_intent_field_changes() -> None:
    k1 = ExplainerCache.key_for(_intent(rpm=3000.0), _result())
    k2 = ExplainerCache.key_for(_intent(rpm=4000.0), _result())
    assert k1 != k2


def test_key_handles_infinite_safety_factor() -> None:
    intent = _intent()
    result = _result(sf=math.inf, stress_pa=0.0)
    # Must not raise
    key = ExplainerCache.key_for(intent, result)
    assert isinstance(key, str)
    assert len(key) == 16


def test_clear_empties_cache() -> None:
    cache = ExplainerCache()
    cache.put("k", NaturalReport(summary="x"))
    cache.clear()
    assert cache.get("k") is None
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_cache.py -v`
Expected: ImportError on `services.explainer.cache`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/cache.py`

```python
"""In-memory cache for the explainer keyed by intent + analysis values."""
from __future__ import annotations

import hashlib
import json
import math

from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class ExplainerCache:
    def __init__(self) -> None:
        self._store: dict[str, NaturalReport] = {}

    @staticmethod
    def key_for(intent: DesignIntent, result: AnalysisResult) -> str:
        # safety_factor may be math.inf for zero-load cases; json.dumps would
        # reject that, so store as string when not finite.
        sf_canonical: str | float
        if math.isfinite(result.safety_factor):
            sf_canonical = round(result.safety_factor, 6)
        else:
            sf_canonical = "inf"
        canonical = {
            "intent_type": intent.type,
            "intent_fields": {
                k: f.value
                for k, f in sorted(intent.fields.items())
                if f.value is not None
            },
            "stress_max_pa": round(result.stress_max_pa, 6),
            "safety_factor": sf_canonical,
            "verdict": result.verdict.value,
            "material": result.material_name,
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> NaturalReport | None:
        return self._store.get(key)

    def put(self, key: str, report: NaturalReport) -> None:
        self._store[key] = report

    def clear(self) -> None:
        self._store.clear()
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_cache.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/explainer/cache.py \
        apps/backend/tests/unit/explainer/test_cache.py
git commit -m "feat(explainer): add in-memory cache keyed by intent+analysis values"
```

---

## Task 8: Generator + ExplainEvent

**Files:**
- Create: `apps/backend/services/explainer/generator.py`
- Create: `apps/backend/tests/unit/explainer/test_generator.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/explainer/test_generator.py`

```python
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
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/unit/explainer/test_generator.py -v`
Expected: ImportError on `services.explainer.generator`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/generator.py`

```python
"""Streaming generator that turns AnalysisResult into NaturalReport via Gemma."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from services.explainer.cache import ExplainerCache
from services.explainer.domain.errors import (
    ExplainError,
    ExplainErrorCode,
)
from services.explainer.domain.models import NaturalReport
from services.explainer.facts import build_facts
from services.explainer.prompt import build_strict_retry_prompt, build_user_prompt
from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class GemmaTextClient(Protocol):
    async def generate_text_streaming(
        self, *, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]: ...


class ExplainEvent(BaseModel):
    event: str       # "progress" | "chunk" | "final" | "error"
    data: dict[str, Any]


class Explainer:
    def __init__(
        self,
        *,
        gemma: GemmaTextClient,
        cache: ExplainerCache,
        system_prompt: str,
    ) -> None:
        self._gemma = gemma
        self._cache = cache
        self._system = system_prompt

    async def explain_streaming(
        self, intent: DesignIntent, result: AnalysisResult
    ) -> AsyncIterator[ExplainEvent]:
        key = self._cache.key_for(intent, result)
        cached = self._cache.get(key)
        if cached is not None:
            yield ExplainEvent(
                event="final",
                data={"report": cached.model_dump(), "cache_hit": True, "cache_key": key},
            )
            return

        facts = build_facts(intent, result)
        yield ExplainEvent(event="progress", data={"step": "generating"})

        accumulated = ""
        try:
            async for chunk in self._gemma.generate_text_streaming(
                system_prompt=self._system,
                user_prompt=build_user_prompt(facts),
            ):
                accumulated += chunk
                yield ExplainEvent(event="chunk", data={"text": chunk})
        except VertexTimeout as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_TIMEOUT,
                message="Vertex AI streaming timed out",
                retry_after=5,
            ).raise_as()
            raise AssertionError("unreachable") from exc
        except VertexRateLimited as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_RATE_LIMITED,
                message=str(exc),
                retry_after=30,
            ).raise_as()
            raise AssertionError("unreachable") from exc
        except Exception as exc:
            ExplainError(
                code=ExplainErrorCode.GEMMA_FAILED,
                message=f"Vertex AI call failed: {exc!r}",
                retry_after=10,
                details={"exception_type": type(exc).__name__},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        yield ExplainEvent(event="progress", data={"step": "parsing"})

        report = await self._parse_or_retry(accumulated, facts)

        self._cache.put(key, report)
        yield ExplainEvent(
            event="final",
            data={"report": report.model_dump(), "cache_hit": False, "cache_key": key},
        )

    async def _parse_or_retry(
        self, first_text: str, facts: dict[str, str]
    ) -> NaturalReport:
        first = _try_parse(first_text)
        if first is not None:
            return first

        retry_text = ""
        try:
            async for chunk in self._gemma.generate_text_streaming(
                system_prompt=self._system,
                user_prompt=build_strict_retry_prompt(facts),
            ):
                retry_text += chunk
        except (VertexTimeout, VertexRateLimited, Exception) as exc:  # noqa: BLE001
            ExplainError(
                code=ExplainErrorCode.REPORT_PARSE_FAILED,
                message=f"Retry stream failed: {exc!r}",
                details={"first_text": first_text[:500]},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        second = _try_parse(retry_text)
        if second is not None:
            return second

        ExplainError(
            code=ExplainErrorCode.REPORT_PARSE_FAILED,
            message="Gemma returned malformed JSON twice",
            details={"first_text": first_text[:500], "retry_text": retry_text[:500]},
        ).raise_as()
        raise AssertionError("unreachable")


def _try_parse(text: str) -> NaturalReport | None:
    stripped = _strip_codefence(text)
    try:
        return NaturalReport.model_validate_json(stripped)
    except (ValidationError, json.JSONDecodeError):
        return None


def _strip_codefence(text: str) -> str:
    """Strip ```json ... ``` if the model wrapped JSON in a code fence."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
    if s.startswith("json\n"):
        s = s[5:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/unit/explainer/test_generator.py -v`
Expected: 9 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/explainer tests/unit/explainer tests/fakes
uv run mypy services/explainer
```
Expected: `All checks passed!` and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/explainer/generator.py \
        apps/backend/tests/unit/explainer/test_generator.py
git commit -m "feat(explainer): add streaming generator with retry-once on malformed JSON"
```

---

## Task 9: API Router (POST /explain SSE)

**Files:**
- Create: `apps/backend/services/explainer/api/__init__.py` (empty)
- Create: `apps/backend/services/explainer/api/router.py`
- Create: `apps/backend/tests/component/explainer/__init__.py` (empty)
- Create: `apps/backend/tests/component/explainer/test_router.py`

- [ ] **Step 1: Write the failing component test** — `apps/backend/tests/component/explainer/test_router.py`

```python
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
            "rpm": {"value": 3000.0, "source": "extracted", "unit": None, "original_text": None, "reason": None},
            "outer_diameter_m": {"value": 0.5, "source": "extracted", "unit": None, "original_text": None, "reason": None},
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
    r = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
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
    # First call populates the cache
    client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    # Second call must hit the cache
    r = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    events = _parse_sse_events(r.text)
    assert [ev["event"] for ev in events] == ["final"]
    assert events[0]["data"]["cache_hit"] is True


def test_explain_invalid_body_returns_422() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    r = client.post("/explain", json={"intent": {"type": "Flywheel_Rim"}})  # missing analysis_result
    assert r.status_code == 422


def test_explain_malformed_json_twice_emits_error_event() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[["bad"], ["still bad"]])
    client = TestClient(_make_app(fake))
    r = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    events = _parse_sse_events(r.text)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "report_parse_failed"


def test_explain_unknown_intent_type_propagates_parse_path() -> None:
    # The router does NOT validate intent type itself; it forwards everything to the explainer.
    # If Gemma cannot produce JSON we get report_parse_failed regardless.
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    intent = _flywheel_intent_dict()
    intent["type"] = "Unknown_Thing"
    r = client.post("/explain", json={"intent": intent, "analysis_result": _analysis_dict()})
    assert r.status_code == 200  # SSE; behavioral check below
    events = _parse_sse_events(r.text)
    assert events[-1]["event"] == "final"  # FakeGemma returns valid JSON regardless


def test_explain_final_data_contains_facts_used() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    client = TestClient(_make_app(fake))
    r = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    events = _parse_sse_events(r.text)
    final = events[-1]
    assert final["event"] == "final"
    assert final["data"]["report"]["facts_used"] == ["safety_factor"]


def test_explain_cache_key_is_stable_across_calls() -> None:
    fake = FakeGemmaTextClient(chunks_per_call=[[_VALID_JSON]])
    app = _make_app(fake)
    client = TestClient(app)
    r1 = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    r2 = client.post("/explain", json={"intent": _flywheel_intent_dict(), "analysis_result": _analysis_dict()})
    k1 = _parse_sse_events(r1.text)[-1]["data"]["cache_key"]
    k2 = _parse_sse_events(r2.text)[-1]["data"]["cache_key"]
    assert k1 == k2
```

- [ ] **Step 2: Run and confirm FAIL**

Run: `uv run pytest tests/component/explainer/test_router.py -v`
Expected: ImportError on `services.explainer.api.router`.

- [ ] **Step 3: Write production code** — `apps/backend/services/explainer/api/router.py`

```python
"""POST /explain router with SSE event stream."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse

from services.explainer.domain.errors import ExplainException
from services.explainer.domain.models import ExplainRequest
from services.explainer.generator import Explainer, ExplainEvent

_logger = structlog.get_logger("explainer.router")

router = APIRouter(tags=["explainer"])


def _serialize(event: ExplainEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, separators=(',', ':'))}\n\n"


async def _stream(
    explainer: Explainer, intent, analysis_result
) -> AsyncIterator[str]:
    try:
        async for event in explainer.explain_streaming(intent, analysis_result):
            yield _serialize(event)
    except ExplainException as exc:
        _logger.warning(
            "explain_failed",
            code=exc.error.code.value,
            intent_type=intent.type,
        )
        err = ExplainEvent(event="error", data=exc.error.model_dump())
        yield _serialize(err)


@router.post("/explain")
async def explain(req: ExplainRequest, app_req: Request) -> StreamingResponse:
    explainer: Explainer = app_req.app.state.explainer
    _logger.info(
        "explain_request_started",
        intent_type=req.intent.type,
        verdict=req.analysis_result.verdict.value,
        session_id=req.session_id,
    )
    return StreamingResponse(
        _stream(explainer, req.intent, req.analysis_result),
        media_type="text/event-stream",
    )


def register_explainer_router(app: FastAPI) -> None:
    """Attach the explainer router. Caller wires app.state.explainer."""
    app.include_router(router)
```

- [ ] **Step 4: Run and confirm PASS**

Run: `uv run pytest tests/component/explainer/test_router.py -v`
Expected: 7 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/explainer tests/unit/explainer tests/component/explainer tests/fakes
uv run mypy services/explainer
```
Expected: `All checks passed!` and `Success`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/explainer/api/__init__.py \
        apps/backend/services/explainer/api/router.py \
        apps/backend/tests/component/explainer/__init__.py \
        apps/backend/tests/component/explainer/test_router.py
git commit -m "feat(explainer): add POST /explain router with SSE event stream"
```

---

## Task 10: Wire S4 in main.py

**Files:**
- Modify: `apps/backend/main.py`

- [ ] **Step 1: Read the bottom of `main.py`**

Run: `tail -n 30 apps/backend/main.py`

Locate the `# --- Wire S3 Physics ---` block. The new block goes immediately after it.

- [ ] **Step 2: Append the S4 wiring**

Add to `apps/backend/main.py`:

```python

# --- Wire S4 Explainer ---
from services.explainer.api.router import register_explainer_router  # noqa: E402
from services.explainer.cache import ExplainerCache  # noqa: E402
from services.explainer.generator import Explainer  # noqa: E402
from services.explainer.prompt import load_system_prompt  # noqa: E402

_explainer_gemma = VertexGemmaClient(
    project_id=settings.gcp_project_id,
    region=settings.gcp_region,
    model_name=settings.vertex_ai_endpoint,
    temperature=0.3,
    max_output_tokens=2048,
)
_explainer = Explainer(
    gemma=_explainer_gemma,
    cache=ExplainerCache(),
    system_prompt=load_system_prompt(BACKEND_ROOT / "prompts"),
)
app.state.explainer = _explainer
register_explainer_router(app)
```

- [ ] **Step 3: Syntactic verification (env vars likely block full boot)**

Run from `apps/backend/`:
```bash
uv run python -c "import ast; ast.parse(open('main.py').read()); print('parsed OK')"
```
Expected: `parsed OK`.

If the environment provides the Settings env vars (`gcp_project_id`, `gcp_region`, `vertex_ai_endpoint`, `gcs_bucket_artifacts`), additionally run:
```bash
uv run python -c "
from main import app
routes = sorted({r.path for r in app.routes})
assert '/explain' in routes, routes
print('OK /explain mounted')
"
```
Expected: `OK /explain mounted`. If env vars are missing this step is skipped; that is acceptable.

- [ ] **Step 4: Standalone verification** (always works, no env vars needed)

```bash
uv run python -c "
from fastapi import FastAPI
from services.explainer.api.router import register_explainer_router
app = FastAPI()
register_explainer_router(app)
routes = sorted({r.path for r in app.routes})
print('routes:', routes)
assert '/explain' in routes
print('OK /explain registered')
"
```
Expected output contains `OK /explain registered`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/main.py
git commit -m "feat(explainer): mount S4 router on main app"
```

---

## Task 11: Integration tests + README + final gate

**Files:**
- Create: `apps/backend/tests/integration/explainer/__init__.py` (empty)
- Create: `apps/backend/tests/integration/explainer/conftest.py`
- Create: `apps/backend/tests/integration/explainer/test_hero_explanations.py`
- Create: `apps/backend/services/explainer/README.md`

- [ ] **Step 1: Write the conftest** — `apps/backend/tests/integration/explainer/conftest.py`

```python
"""Hero (DesignIntent, AnalysisResult) fixtures for S4 integration tests."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.explainer.api.router import register_explainer_router
from services.explainer.cache import ExplainerCache
from services.explainer.generator import Explainer
from services.explainer.prompt import load_system_prompt
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gemma_text import FakeGemmaTextClient

_BACKEND = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _BACKEND / "prompts"


def _f(value: float, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


HERO_INTENTS: dict[str, DesignIntent] = {
    "flywheel": DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(3000.0),
        },
        composed_of=[],
    ),
    "hydro": DesignIntent(
        type="Pelton_Runner",
        fields={
            "runner_diameter_m": _f(0.8),
            "bucket_count": _f(20.0),
            "head_m": _f(20.0),
            "flow_m3_s": _f(0.5),
        },
        composed_of=[],
    ),
    "shelter": DesignIntent(
        type="Hinge_Panel",
        fields={
            "width_m": _f(1.0),
            "height_m": _f(2.0),
            "thickness_m": _f(0.02),
            "wind_kmh": _f(100.0),
        },
        composed_of=[],
    ),
}


HERO_RESULTS: dict[str, AnalysisResult] = {
    "flywheel": AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159, "outer_diameter_m": 0.5},
    ),
    "hydro": AnalysisResult(
        intent_type="Pelton_Runner",
        material_name="stainless_304",
        material_yield_mpa=215.0,
        formula="tau = 16T/(pi*d^3)",
        stress_max_pa=8.0e7,
        displacement_max_m=2.5e-4,
        safety_factor=1.55,
        verdict=Verdict.WARN,
        inputs={"head_m": 20.0, "flow_m3_s": 0.5},
    ),
    "shelter": AnalysisResult(
        intent_type="Hinge_Panel",
        material_name="bamboo_laminated",
        material_yield_mpa=60.0,
        formula="sigma = 6*P*L^2/t^2",
        stress_max_pa=2.0e7,
        displacement_max_m=1.5e-3,
        safety_factor=3.0,
        verdict=Verdict.PASS,
        inputs={"wind_speed_m_s": 27.78, "pressure_pa": 378.5},
    ),
}


def _valid_report_json(summary: str, facts_used: list[str]) -> str:
    return json.dumps(
        {
            "summary": summary,
            "risks": ["risk"],
            "suggestions": ["suggestion"],
            "analogies": ["analogy"],
            "facts_used": facts_used,
        }
    )


@pytest.fixture(scope="module")
def explain_client() -> Iterable[TestClient]:
    fake = FakeGemmaTextClient(
        chunks_per_call=[[_valid_report_json("hero narrative", ["safety_factor", "verdict"])]] * 10
    )
    app = FastAPI()
    explainer = Explainer(
        gemma=fake,
        cache=ExplainerCache(),
        system_prompt=load_system_prompt(_PROMPTS_DIR),
    )
    app.state.explainer = explainer
    register_explainer_router(app)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def hero_intent_flywheel() -> DesignIntent:
    return HERO_INTENTS["flywheel"]


@pytest.fixture
def hero_result_flywheel() -> AnalysisResult:
    return HERO_RESULTS["flywheel"]


@pytest.fixture
def hero_intent_hydro() -> DesignIntent:
    return HERO_INTENTS["hydro"]


@pytest.fixture
def hero_result_hydro() -> AnalysisResult:
    return HERO_RESULTS["hydro"]


@pytest.fixture
def hero_intent_shelter() -> DesignIntent:
    return HERO_INTENTS["shelter"]


@pytest.fixture
def hero_result_shelter() -> AnalysisResult:
    return HERO_RESULTS["shelter"]
```

- [ ] **Step 2: Write the integration tests** — `apps/backend/tests/integration/explainer/test_hero_explanations.py`

```python
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
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/integration/explainer -m integration -v`
Expected: 3 passed.

- [ ] **Step 4: Write the README** — `apps/backend/services/explainer/README.md`

```markdown
# S4 Explainer

Sync analytical narration. Maps `DesignIntent + AnalysisResult` (from S1 + S3)
to a `NaturalReport` produced by Gemma 4 (grounded, temperature 0.3), streamed
over Server-Sent Events.

See the [design spec](../../../../docs/superpowers/specs/2026-05-16-s4-explainer-design.md)
for context.

## Endpoint

- `POST /explain` -- SSE. Body: `{ intent: DesignIntent, analysis_result: AnalysisResult, session_id?: string }`

```bash
curl -N -X POST http://localhost:8080/explain \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "type": "Flywheel_Rim",
      "fields": {
        "outer_diameter_m": {"value": 0.5, "source": "extracted"},
        "rpm": {"value": 3000, "source": "extracted"}
      },
      "composed_of": []
    },
    "analysis_result": {
      "intent_type": "Flywheel_Rim",
      "material_name": "steel_a36",
      "material_yield_mpa": 250,
      "formula": "sigma = rho*omega^2*R^2",
      "stress_max_pa": 193700000,
      "displacement_max_m": 0.00048,
      "safety_factor": 1.29,
      "verdict": "warn",
      "inputs": {}
    }
  }'
```

## SSE events

- `progress` -- `{step: "generating" | "parsing"}`
- `chunk` -- `{text: "..."}` raw Gemma text as it arrives
- `final` -- `{report: NaturalReport, cache_hit: boolean, cache_key: string}`
- `error` -- `{code: ExplainErrorCode, message, retry_after?, details?}`

Stream always ends with exactly one `final` or `error`.

## NaturalReport schema

```json
{
  "summary":     "<<=80 word plain-English summary>",
  "risks":       ["..."],
  "suggestions": ["..."],
  "analogies":   ["..."],
  "facts_used":  ["safety_factor", "stress_max_mpa", ...]
}
```

Every numeric value cited in the prose appears in `facts_used`. Gemma is
contractually forbidden from inventing numbers; if a value is not in the
FACTS table prepended to the user prompt, it writes "(not available)".

## Local development

```bash
cd apps/backend
uv run pytest tests/unit/explainer tests/component/explainer -v
uv run pytest tests/integration/explainer -m integration -v
```

## Runbook: Vertex unavailable

The explainer returns:
- `gemma_timeout` (HTTP 504-equivalent in SSE error) if Vertex times out before the first chunk
- `gemma_rate_limited` (HTTP 429) on quota exhausted
- `gemma_failed` (HTTP 502) on any other Vertex error

The client retries with the suggested `retry_after`. No server-side retry on
Vertex failures. JSON parse failures are retried once with a stricter prompt.

## Out of scope (deferred)

- Bilingual ES + EN -- English only for MVP
- GCS-persisted cache -- only in-memory
- Pre-baked hero report files -- optional stretch goal
- Multi-turn refinement -- separate plan
```

- [ ] **Step 5: Run the full S4 gate**

From `apps/backend/`:
```bash
uv run ruff check services/explainer tests/unit/explainer tests/component/explainer tests/integration/explainer tests/fakes
uv run mypy services/explainer
uv run pytest tests/unit/explainer tests/component/explainer --cov=services/explainer --cov-report=term-missing --cov-fail-under=85 -q
uv run pytest tests/integration/explainer -m integration -q
```
Expected:
- ruff: `All checks passed!`
- mypy: `Success: no issues found`
- coverage gate: `Required test coverage of 85% reached.`
- integration: 3 passed

If coverage is under 85%, identify the gap in `term-missing` output. Common spots: the `Exception` bridge branches in `generator.py` (rare exceptions during retry stream), the `_strip_codefence` `s.startswith("json\n")` branch, the cache `clear()` method. Add targeted unit tests before committing.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/explainer/README.md \
        apps/backend/tests/integration/explainer/__init__.py \
        apps/backend/tests/integration/explainer/conftest.py \
        apps/backend/tests/integration/explainer/test_hero_explanations.py
git commit -m "test(explainer): add integration tests for 3 heroes + README"
```

If you had to add coverage tests, include them in the same commit OR a separate `test(explainer): add coverage tests for <area>`.

---

## Done criteria

All of the following hold:

- [ ] Tasks 1-11 commits land in order, each green at commit time
- [ ] `uv run ruff check services/explainer ...` exits 0
- [ ] `uv run mypy services/explainer` exits 0
- [ ] `uv run pytest tests/unit/explainer tests/component/explainer --cov-fail-under=85` exits 0
- [ ] `uv run pytest tests/integration/explainer -m integration` exits 0 with 3/3
- [ ] `POST /explain` route registered (verified via the standalone `register_explainer_router` boot)
- [ ] README + spec docs committed
- [ ] No edits to `services/{geometry,physics}/`
- [ ] No edits to `services/interpreter/` other than `gemma_client.py` (two sentinel classes added) and `vertex_gemma.py` (one new method + new import)

## Out of scope for this plan

- Frontend hook `useExplainStream` (separate plan)
- S5 Documenter
- Live Vertex AI smoke from this session (needs correct GCP project, user-owned)
- Bilingual ES + EN
- GCS-persisted cache
- Pre-baked hero report fallbacks

## Notes for the executor

- DO NOT use `--no-verify` on commits.
- DO NOT add `Co-Authored-By` lines.
- DO NOT touch `services/geometry/` or `services/physics/`.
- DO NOT add or modify any code in `services/interpreter/` except the two extension points listed in Tasks 3 and 4 (`gemma_client.py` sentinel exceptions, `vertex_gemma.py` new method + import).
- Run all commands from `apps/backend/` and use `uv run`.
- ASCII-only in code strings and docstrings (`sigma`, `rho`, `omega`, etc.). Ruff flags Greek as RUF001/RUF002.
- If `ruff check` reports `B904` on a `raise AssertionError("unreachable")` inside `except`, add `from None` or `from exc`. This is the same convention applied in S3 solvers.
- If a step's expected output does not match, STOP and report. Do not muddle through.
- After Task 11 passes, append a one-line entry to project root `CLAUDE.md` under "Implementation status" that S4 (English-only, in-memory cache) is live. Do NOT do this until all gates are green.
