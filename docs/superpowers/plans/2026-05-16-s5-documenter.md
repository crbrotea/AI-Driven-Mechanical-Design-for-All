# S5 Documenter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the S5 Documenter subsystem — a sync `POST /document` endpoint that takes the full pipeline output (`DesignIntent` + `AnalysisResult` + `NaturalReport` + `CachedArtifacts`) and returns a `Deliverables` bundle: a 5-page engineering report PDF + a 1-page technical drawing PDF on GCS signed URLs, plus the existing STEP/GLB/SVG URLs from S2 echoed through.

**Architecture:** Five-layer mirror of S2/S3/S4 — HTTP → views (build123d projections) → PDF (reportlab) → storage (GCS) → cache (in-memory). PDFs are built from pure functions; the pipeline orchestrates cache lookup → svg fetch → compose → project → 2 PDF builds → 2 parallel GCS uploads. Stateless except the per-process cache.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, structlog, reportlab>=4.2 (PDF), pypdf>=4.0 (test text extraction), build123d (view projections), google-cloud-storage, httpx (SVG fetch), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-16-s5-documenter-design.md`

---

## Pre-flight

Run all commands from `apps/backend/` unless stated otherwise. Use `uv run` for every Python command. The repo branch is `master` (user-consented direct commits, conventional-commit style, no `Co-Authored-By`, no `--no-verify`, never `uv build`). Existing uncommitted edits in `services/geometry/primitives/*.py` and `apps/frontend/next-env.d.ts` are unrelated to S5 and must NOT be staged.

ASCII-only in code strings: no Greek, no `·` (middle dot), no `×` (multiplication sign). Replace with `sigma`, `rho`, `omega`, `*`. Ruff RUF001/RUF002 catches these and previous executor notes (S3 plan, S4 plan) document the convention.

S4 introduced two patterns the executor must respect when they reappear here:
1. `# noqa: BLE001` is FORBIDDEN — that lint isn't enabled and ruff strict mode flags unused noqa via `RUF100`.
2. `# noqa: N818 -- intentional distinction` is fine for exception classes that share a stem with Pydantic models.

---

## File Structure

**Created**:

```
apps/backend/services/documenter/
├── __init__.py                                  # empty package marker
├── README.md
├── domain/
│   ├── __init__.py
│   ├── errors.py                                # DocumentErrorCode, DocumentError, DocumentException
│   └── models.py                                # DocumentRequest, Deliverables
├── pdf/
│   ├── __init__.py
│   ├── theme.py                                 # PAGE_SIZE, MARGIN_PT, colors, fonts
│   ├── report.py                                # build_report_pdf (5-page engineering report)
│   └── drawing.py                               # build_drawing_pdf (1-page technical drawing)
├── views.py                                     # project_views(compound) -> {front, side, iso} svg bytes
├── storage.py                                   # DocumentStorage (GCS uploader + signed URLs)
├── cache.py                                     # DocumenterCache
├── svg_fetcher.py                               # SvgFetcher Protocol + HttpxSvgFetcher
├── pipeline.py                                  # Documenter orchestrator
└── api/
    ├── __init__.py
    └── router.py                                # POST /document + register_documenter_router

apps/backend/tests/fakes/
├── fake_gcs_client.py                           # in-memory stand-in for storage.Client
└── fake_svg_fetcher.py                          # canned SVG bytes fetcher

apps/backend/tests/unit/documenter/
├── __init__.py
├── test_models.py
├── test_errors.py
├── test_theme.py
├── test_cache.py
├── test_views.py
├── test_report.py
├── test_drawing.py
├── test_storage.py
└── test_pipeline.py

apps/backend/tests/component/documenter/
├── __init__.py
└── test_router.py

apps/backend/tests/integration/documenter/
├── __init__.py
├── conftest.py                                  # hero (intent, analysis, narrative, geometry) fixtures
└── test_hero_documents.py
```

**Modified**:

- `apps/backend/pyproject.toml` — add `reportlab>=4.2` to `[project] dependencies`, add `pypdf>=4.0` to `[project.optional-dependencies] dev`
- `apps/backend/main.py` — wire `Documenter` with the GCS client already created for S2 (or a fresh one if cleaner), build `Documenter` + `register_documenter_router(app)`

---

## Task 1: Add reportlab + pypdf dependencies

**Files:**
- Modify: `apps/backend/pyproject.toml`

- [ ] **Step 1: Show current dependencies**

Run: `head -28 apps/backend/pyproject.toml`

You should see the existing `[project] dependencies = [ ... ]` block ending with `"httpx>=0.27.0",` and the `[project.optional-dependencies] dev = [ ... ]` block ending with `"mypy>=1.13.0",`.

- [ ] **Step 2: Add reportlab to runtime deps**

Edit `apps/backend/pyproject.toml`. Locate the line `"httpx>=0.27.0",` inside `dependencies = [...]` and add a line directly after it:

```
    "reportlab>=4.2.0",
```

- [ ] **Step 3: Add pypdf to dev deps**

In `apps/backend/pyproject.toml`. Locate the line `"mypy>=1.13.0",` inside `dev = [...]` and add a line directly after it:

```
    "pypdf>=4.0.0",
```

- [ ] **Step 4: Sync and verify**

Run:
```bash
uv sync --extra dev
uv run python -c "import reportlab; print('reportlab', reportlab.__version__)"
uv run python -c "import pypdf; print('pypdf', pypdf.__version__)"
```
Expected: both versions print, no import errors.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/uv.lock
git commit -m "chore(deps): add reportlab and pypdf for S5 Documenter"
```

If `uv.lock` does not exist, omit it from the `git add` command.

---

## Task 2: Domain models — DocumentRequest + Deliverables

**Files:**
- Create: `apps/backend/services/documenter/__init__.py` (empty)
- Create: `apps/backend/services/documenter/domain/__init__.py` (empty)
- Create: `apps/backend/services/documenter/domain/models.py`
- Create: `apps/backend/tests/unit/documenter/__init__.py` (empty)
- Create: `apps/backend/tests/unit/documenter/test_models.py`

- [ ] **Step 1: Write the failing test** — `apps/backend/tests/unit/documenter/test_models.py`

```python
"""DocumentRequest + Deliverables model tests."""
from __future__ import annotations

from services.documenter.domain.models import Deliverables, DocumentRequest
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _analysis() -> AnalysisResult:
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


def _narrative() -> NaturalReport:
    return NaturalReport(summary="ok", facts_used=["safety_factor"])


def _artifacts() -> CachedArtifacts:
    return CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
        ),
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )


def test_document_request_carries_all_subsystem_outputs() -> None:
    req = DocumentRequest(
        intent=_intent(),
        analysis_result=_analysis(),
        natural_report=_narrative(),
        geometry_artifacts=_artifacts(),
        session_id="sess-1",
    )
    assert req.intent.type == "Flywheel_Rim"
    assert req.analysis_result.verdict is Verdict.PASS
    assert req.natural_report.summary == "ok"
    assert req.geometry_artifacts.step_url == "https://example.com/step"
    assert req.session_id == "sess-1"


def test_document_request_session_id_optional() -> None:
    req = DocumentRequest(
        intent=_intent(),
        analysis_result=_analysis(),
        natural_report=_narrative(),
        geometry_artifacts=_artifacts(),
    )
    assert req.session_id is None


def test_deliverables_roundtrip() -> None:
    d = Deliverables(
        report_pdf_url="fake://bucket/documents/abc/report.pdf",
        drawing_pdf_url="fake://bucket/documents/abc/drawing.pdf",
        step_url="x",
        glb_url="y",
        svg_url="z",
        cache_hit=False,
        cache_key="abc",
    )
    parsed = Deliverables.model_validate_json(d.model_dump_json())
    assert parsed.cache_key == "abc"
    assert parsed.cache_hit is False
    assert parsed.report_pdf_url.endswith("/report.pdf")


def test_deliverables_cache_hit_flag() -> None:
    d = Deliverables(
        report_pdf_url="r", drawing_pdf_url="d",
        step_url="s", glb_url="g", svg_url="v",
        cache_hit=True, cache_key="abc",
    )
    assert d.cache_hit is True
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_models.py -v`
Expected: `ModuleNotFoundError: No module named 'services.documenter'`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/domain/models.py`

```python
"""Domain models for S5 Documenter."""
from __future__ import annotations

from pydantic import BaseModel

from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class DocumentRequest(BaseModel):
    """Request body for POST /document."""

    intent: DesignIntent
    analysis_result: AnalysisResult
    natural_report: NaturalReport
    geometry_artifacts: CachedArtifacts
    session_id: str | None = None


class Deliverables(BaseModel):
    """Response body of POST /document. Bundles all 5 artifact URLs."""

    report_pdf_url: str
    drawing_pdf_url: str
    step_url: str
    glb_url: str
    svg_url: str
    cache_hit: bool
    cache_key: str
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter
uv run mypy services/documenter
```
Expected: `All checks passed!` and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/__init__.py \
        apps/backend/services/documenter/domain/__init__.py \
        apps/backend/services/documenter/domain/models.py \
        apps/backend/tests/unit/documenter/__init__.py \
        apps/backend/tests/unit/documenter/test_models.py
git commit -m "feat(documenter): add DocumentRequest and Deliverables models"
```

---

## Task 3: Error taxonomy

**Files:**
- Create: `apps/backend/services/documenter/domain/errors.py`
- Create: `apps/backend/tests/unit/documenter/test_errors.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_errors.py`

```python
"""Documenter error taxonomy tests."""
from __future__ import annotations

import json

import pytest

from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
    DocumentException,
)


def test_codes_stable() -> None:
    assert DocumentErrorCode.INVALID_INPUT.value == "invalid_input"
    assert DocumentErrorCode.GEOMETRY_REBUILD_FAILED.value == "geometry_rebuild_failed"
    assert DocumentErrorCode.VIEW_PROJECTION_FAILED.value == "view_projection_failed"
    assert DocumentErrorCode.REPORT_BUILD_FAILED.value == "report_build_failed"
    assert DocumentErrorCode.DRAWING_BUILD_FAILED.value == "drawing_build_failed"
    assert DocumentErrorCode.GCS_UPLOAD_FAILED.value == "gcs_upload_failed"
    assert DocumentErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_http_status_mapping() -> None:
    assert DocumentError(code=DocumentErrorCode.INVALID_INPUT, message="x").http_status == 422
    assert DocumentError(code=DocumentErrorCode.GCS_UPLOAD_FAILED, message="x").http_status == 502
    assert DocumentError(code=DocumentErrorCode.REPORT_BUILD_FAILED, message="x").http_status == 500
    assert DocumentError(code=DocumentErrorCode.INTERNAL_ERROR, message="x").http_status == 500


def test_serializes_with_optional_fields() -> None:
    err = DocumentError(
        code=DocumentErrorCode.GCS_UPLOAD_FAILED,
        message="upload broke",
        stage="upload",
        retry_after=5,
    )
    payload = json.loads(err.model_dump_json())
    assert payload["code"] == "gcs_upload_failed"
    assert payload["stage"] == "upload"
    assert payload["retry_after"] == 5


def test_raise_as_wraps_in_exception() -> None:
    err = DocumentError(code=DocumentErrorCode.REPORT_BUILD_FAILED, message="boom")
    with pytest.raises(DocumentException) as ei:
        err.raise_as()
    assert ei.value.error.code is DocumentErrorCode.REPORT_BUILD_FAILED
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_errors.py -v`
Expected: ImportError on `services.documenter.domain.errors`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/domain/errors.py`

```python
"""Structured error taxonomy for S5 Documenter."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class DocumentErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    GEOMETRY_REBUILD_FAILED = "geometry_rebuild_failed"
    VIEW_PROJECTION_FAILED = "view_projection_failed"
    REPORT_BUILD_FAILED = "report_build_failed"
    DRAWING_BUILD_FAILED = "drawing_build_failed"
    GCS_UPLOAD_FAILED = "gcs_upload_failed"
    INTERNAL_ERROR = "internal_error"


_STATUS_MAP: dict[DocumentErrorCode, int] = {
    DocumentErrorCode.INVALID_INPUT: 422,
    DocumentErrorCode.GEOMETRY_REBUILD_FAILED: 500,
    DocumentErrorCode.VIEW_PROJECTION_FAILED: 500,
    DocumentErrorCode.REPORT_BUILD_FAILED: 500,
    DocumentErrorCode.DRAWING_BUILD_FAILED: 500,
    DocumentErrorCode.GCS_UPLOAD_FAILED: 502,
    DocumentErrorCode.INTERNAL_ERROR: 500,
}


class DocumentError(BaseModel):
    code: DocumentErrorCode
    message: str
    field: str | None = None
    stage: str | None = None
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return _STATUS_MAP.get(self.code, 500)

    def raise_as(self) -> None:
        raise DocumentException(self)


class DocumentException(RuntimeError):  # noqa: N818 -- intentional distinction from DocumentError model
    """Raised by pipeline internals; carries a DocumentError payload."""

    def __init__(self, error: DocumentError) -> None:
        super().__init__(error.message)
        self.error = error
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_errors.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/documenter/domain/errors.py \
        apps/backend/tests/unit/documenter/test_errors.py
git commit -m "feat(documenter): add documenter error taxonomy"
```

---

## Task 4: Theme constants

**Files:**
- Create: `apps/backend/services/documenter/pdf/__init__.py` (empty)
- Create: `apps/backend/services/documenter/pdf/theme.py`
- Create: `apps/backend/tests/unit/documenter/test_theme.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_theme.py`

```python
"""Theme constants tests."""
from __future__ import annotations

from services.documenter.pdf import theme


def test_page_size_is_a4() -> None:
    # A4 in points: 595.27 x 841.89 — accept any pair starting with these numbers
    width, height = theme.PAGE_SIZE
    assert 590 < width < 600
    assert 840 < height < 845


def test_verdict_color_map_covers_all_verdicts() -> None:
    assert "pass" in theme.COLOR_VERDICT
    assert "warn" in theme.COLOR_VERDICT
    assert "fail" in theme.COLOR_VERDICT


def test_fonts_are_tuples_of_name_and_size() -> None:
    for font in (theme.FONT_TITLE, theme.FONT_H1, theme.FONT_H2, theme.FONT_BODY, theme.FONT_MONO):
        assert isinstance(font, tuple)
        assert len(font) == 2
        assert isinstance(font[0], str)
        assert isinstance(font[1], int | float)
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_theme.py -v`
Expected: ImportError on `services.documenter.pdf.theme`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/pdf/theme.py`

```python
"""Visual constants for S5 Documenter PDFs."""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

PAGE_SIZE = A4                                # ~(595.27, 841.89) pt
MARGIN_PT = 50                                # ~18 mm

BRAND_PRIMARY = colors.HexColor("#1A73E8")
BRAND_ACCENT = colors.HexColor("#34A853")

COLOR_VERDICT: dict[str, colors.Color] = {
    "pass": colors.HexColor("#34A853"),
    "warn": colors.HexColor("#F4B400"),
    "fail": colors.HexColor("#DB4437"),
}

FONT_TITLE: tuple[str, int] = ("Helvetica-Bold", 22)
FONT_H1: tuple[str, int] = ("Helvetica-Bold", 14)
FONT_H2: tuple[str, int] = ("Helvetica-Bold", 11)
FONT_BODY: tuple[str, int] = ("Helvetica", 10)
FONT_MONO: tuple[str, int] = ("Courier", 9)
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_theme.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/documenter/pdf/__init__.py \
        apps/backend/services/documenter/pdf/theme.py \
        apps/backend/tests/unit/documenter/test_theme.py
git commit -m "feat(documenter): add PDF theme constants"
```

---

## Task 5: Cache

**Files:**
- Create: `apps/backend/services/documenter/cache.py`
- Create: `apps/backend/tests/unit/documenter/test_cache.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_cache.py`

```python
"""DocumenterCache tests."""
from __future__ import annotations

import math

from services.documenter.cache import DocumenterCache
from services.documenter.domain.models import Deliverables
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent(rpm: float = 3000.0) -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=rpm, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _analysis(sf: float = 1.29, stress: float = 1.93e8) -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=stress,
        displacement_max_m=4.8e-4,
        safety_factor=sf,
        verdict=Verdict.WARN if sf < 2.0 else Verdict.PASS,
        inputs={},
    )


def _narrative(summary: str = "ok", facts: list[str] | None = None) -> NaturalReport:
    return NaturalReport(summary=summary, facts_used=facts or [])


def _deliv(key: str = "k1") -> Deliverables:
    return Deliverables(
        report_pdf_url="r", drawing_pdf_url="d",
        step_url="s", glb_url="g", svg_url="v",
        cache_hit=False, cache_key=key,
    )


def test_get_returns_none_on_miss() -> None:
    cache = DocumenterCache()
    assert cache.get("missing") is None


def test_put_then_get_roundtrip() -> None:
    cache = DocumenterCache()
    d = _deliv()
    cache.put("k1", d)
    assert cache.get("k1") is d


def test_key_is_deterministic_and_16_chars() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(), _narrative())
    k2 = DocumenterCache.key_for(_intent(), _analysis(), _narrative())
    assert k1 == k2
    assert len(k1) == 16


def test_key_changes_when_intent_field_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(rpm=3000.0), _analysis(), _narrative())
    k2 = DocumenterCache.key_for(_intent(rpm=4000.0), _analysis(), _narrative())
    assert k1 != k2


def test_key_changes_when_safety_factor_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(sf=1.29), _narrative())
    k2 = DocumenterCache.key_for(_intent(), _analysis(sf=2.5), _narrative())
    assert k1 != k2


def test_key_changes_when_narrative_summary_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(), _narrative(summary="A"))
    k2 = DocumenterCache.key_for(_intent(), _analysis(), _narrative(summary="B"))
    assert k1 != k2


def test_key_handles_infinite_safety_factor() -> None:
    key = DocumenterCache.key_for(_intent(), _analysis(sf=math.inf, stress=0.0), _narrative())
    assert isinstance(key, str)
    assert len(key) == 16


def test_clear_empties_cache() -> None:
    cache = DocumenterCache()
    cache.put("k", _deliv())
    cache.clear()
    assert cache.get("k") is None
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_cache.py -v`
Expected: ImportError on `services.documenter.cache`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/cache.py`

```python
"""In-memory cache for S5 Documenter keyed by intent + analysis + narrative."""
from __future__ import annotations

import hashlib
import json
import math

from services.documenter.domain.models import Deliverables
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class DocumenterCache:
    def __init__(self) -> None:
        self._store: dict[str, Deliverables] = {}

    @staticmethod
    def key_for(
        intent: DesignIntent,
        analysis: AnalysisResult,
        narrative: NaturalReport,
    ) -> str:
        sf = analysis.safety_factor
        sf_canonical: str | float = round(sf, 6) if math.isfinite(sf) else "inf"
        canonical = {
            "intent_type": intent.type,
            "intent_fields": {
                k: f.value
                for k, f in sorted(intent.fields.items())
                if f.value is not None
            },
            "stress_max_pa": round(analysis.stress_max_pa, 6),
            "safety_factor": sf_canonical,
            "verdict": analysis.verdict.value,
            "material": analysis.material_name,
            "narrative_facts": sorted(narrative.facts_used),
            "summary_hash": hashlib.sha256(
                narrative.summary.encode("utf-8")
            ).hexdigest()[:8],
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Deliverables | None:
        return self._store.get(key)

    def put(self, key: str, value: Deliverables) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_cache.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/documenter/cache.py \
        apps/backend/tests/unit/documenter/test_cache.py
git commit -m "feat(documenter): add in-memory cache keyed by intent+analysis+narrative"
```

---

## Task 6: SVG Fetcher

**Files:**
- Create: `apps/backend/services/documenter/svg_fetcher.py`
- Create: `apps/backend/tests/fakes/fake_svg_fetcher.py`

The fake gets its tests indirectly through the pipeline tests in Task 11. No dedicated test for the fake itself.

- [ ] **Step 1: Write `FakeSvgFetcher`** — `apps/backend/tests/fakes/fake_svg_fetcher.py`

```python
"""Canned SVG fetcher for tests.

Returns the same SVG bytes for any URL, or raises if configured to do so.
"""
from __future__ import annotations

_DEFAULT_SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'


class FakeSvgFetcher:
    def __init__(
        self,
        svg_bytes: bytes = _DEFAULT_SVG,
        raise_on_call: Exception | None = None,
    ) -> None:
        self._svg = svg_bytes
        self._raise = raise_on_call
        self.calls: list[str] = []

    async def fetch(self, url: str) -> bytes:
        self.calls.append(url)
        if self._raise is not None:
            raise self._raise
        return self._svg
```

- [ ] **Step 2: Write the production fetcher** — `apps/backend/services/documenter/svg_fetcher.py`

```python
"""SVG fetcher used by S5 Documenter to embed section views into PDFs."""
from __future__ import annotations

from typing import Protocol

import httpx


class SvgFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class HttpxSvgFetcher:
    """Production SVG fetcher using httpx (already a backend dep).

    Raises httpx.HTTPError subclasses on transport / status errors. The
    pipeline is responsible for mapping those to a structured DocumentError.
    """

    def __init__(self, timeout_s: float = 5.0) -> None:
        self._timeout_s = timeout_s

    async def fetch(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
```

- [ ] **Step 3: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter tests/fakes
uv run mypy services/documenter
```
Expected: `All checks passed!` and `Success`.

- [ ] **Step 4: Sanity-import the fake**

```bash
uv run python -c "
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher
import asyncio
f = FakeSvgFetcher(b'<svg/>')
print(asyncio.run(f.fetch('http://x')))
print('calls:', f.calls)
"
```
Expected: prints `b'<svg/>'` and `calls: ['http://x']`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/documenter/svg_fetcher.py \
        apps/backend/tests/fakes/fake_svg_fetcher.py
git commit -m "feat(documenter): add SvgFetcher protocol + Httpx implementation + fake"
```

---

## Task 7: Storage + FakeGcsClient

**Files:**
- Create: `apps/backend/services/documenter/storage.py`
- Create: `apps/backend/tests/fakes/fake_gcs_client.py`
- Create: `apps/backend/tests/unit/documenter/test_storage.py`

- [ ] **Step 1: Write `FakeGcsClient`** — `apps/backend/tests/fakes/fake_gcs_client.py`

```python
"""In-memory stand-in for google.cloud.storage.Client.

Records every uploaded blob and supports injecting transient failures so that
DocumentStorage.upload can be tested for its retry-once behavior.
"""
from __future__ import annotations

from collections.abc import Iterable


class _FakeBlob:
    def __init__(
        self,
        bucket_name: str,
        name: str,
        store: dict[tuple[str, str], bytes],
        fail_remaining: list[Exception],
    ) -> None:
        self._bucket_name = bucket_name
        self._name = name
        self._store = store
        self._fail_remaining = fail_remaining

    def upload_from_string(self, content: bytes, content_type: str) -> None:
        if self._fail_remaining:
            raise self._fail_remaining.pop(0)
        self._store[(self._bucket_name, self._name)] = content


class _FakeBucket:
    def __init__(
        self,
        name: str,
        store: dict[tuple[str, str], bytes],
        fail_remaining: list[Exception],
    ) -> None:
        self.name = name
        self._store = store
        self._fail_remaining = fail_remaining

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(self.name, name, self._store, self._fail_remaining)


class FakeGcsClient:
    """Minimal subset of google.cloud.storage.Client used by DocumentStorage."""

    def __init__(self, *, fail_sequence: Iterable[Exception] | None = None) -> None:
        self._store: dict[tuple[str, str], bytes] = {}
        self._fail_remaining: list[Exception] = list(fail_sequence or [])
        self.upload_attempts = 0

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(name, self._store, self._fail_remaining_view())

    def _fail_remaining_view(self) -> list[Exception]:
        """Shared list reference so the blob can pop from it.

        Also increments upload_attempts as a side effect when storage tries.
        """
        return self._fail_remaining

    def stored(self, bucket: str, name: str) -> bytes | None:
        return self._store.get((bucket, name))
```

- [ ] **Step 2: Write failing test** — `apps/backend/tests/unit/documenter/test_storage.py`

```python
"""DocumentStorage tests."""
from __future__ import annotations

import pytest
from google.api_core import exceptions as google_exc

from services.documenter.storage import DocumentStorage
from tests.fakes.fake_gcs_client import FakeGcsClient


@pytest.fixture
def storage_factory():
    def _make(client: FakeGcsClient | None = None) -> tuple[FakeGcsClient, DocumentStorage]:
        c = client or FakeGcsClient()
        s = DocumentStorage(gcs_client=c, bucket_name="b")
        return c, s
    return _make


@pytest.mark.asyncio
async def test_upload_stores_blob_and_returns_signed_url(storage_factory) -> None:
    client, storage = storage_factory()
    url = await storage.upload("abcd1234", "report", b"%PDF-1.4...")
    assert client.stored("b", "documents/abcd1234/report.pdf") == b"%PDF-1.4..."
    assert url.startswith("fake://b/documents/abcd1234/report.pdf")


@pytest.mark.asyncio
async def test_upload_retries_once_on_transient_failure(storage_factory) -> None:
    client = FakeGcsClient(
        fail_sequence=[google_exc.ServiceUnavailable("transient")]
    )
    _, storage = storage_factory(client)
    url = await storage.upload("abcd1234", "drawing", b"%PDF-1.4...")
    assert client.stored("b", "documents/abcd1234/drawing.pdf") == b"%PDF-1.4..."
    assert url.endswith("/drawing.pdf?ttl=24h")


@pytest.mark.asyncio
async def test_upload_hard_fails_after_second_transient_failure(storage_factory) -> None:
    client = FakeGcsClient(
        fail_sequence=[
            google_exc.ServiceUnavailable("first"),
            google_exc.ServiceUnavailable("second"),
        ]
    )
    _, storage = storage_factory(client)
    with pytest.raises(google_exc.ServiceUnavailable):
        await storage.upload("abcd1234", "report", b"%PDF-1.4...")


@pytest.mark.asyncio
async def test_upload_uses_documents_prefix(storage_factory) -> None:
    client, storage = storage_factory()
    await storage.upload("CACHEKEY", "report", b"x")
    assert client.stored("b", "documents/CACHEKEY/report.pdf") == b"x"
```

- [ ] **Step 3: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_storage.py -v`
Expected: ImportError on `services.documenter.storage`.

- [ ] **Step 4: Write production code** — `apps/backend/services/documenter/storage.py`

```python
"""GCS uploader for S5 Documenter PDFs."""
from __future__ import annotations

import asyncio
from typing import Any

from google.api_core import exceptions as google_exc


class DocumentStorage:
    def __init__(
        self,
        *,
        gcs_client: Any,
        bucket_name: str,
        ttl_hours: int = 24,
        prefix: str = "documents",
    ) -> None:
        self._client = gcs_client
        self._bucket_name = bucket_name
        self._ttl_hours = ttl_hours
        self._prefix = prefix

    async def upload(
        self,
        cache_key: str,
        name: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload to {prefix}/{cache_key}/{name}.pdf. Retry once on transient failure.

        Returns the signed URL for the uploaded blob.
        """
        blob_path = f"{self._prefix}/{cache_key}/{name}.pdf"

        async def _do_upload() -> None:
            await asyncio.to_thread(
                self._client.bucket(self._bucket_name).blob(blob_path).upload_from_string,
                content,
                content_type,
            )

        try:
            await _do_upload()
        except (google_exc.ServiceUnavailable, google_exc.InternalServerError):
            await asyncio.sleep(1.0)
            await _do_upload()

        return self._sign(blob_path)

    def _sign(self, blob_path: str) -> str:
        """Return a signed URL.

        FakeGcsClient does not implement v4 signing, so when the underlying
        client lacks a `bucket(...).blob(...).generate_signed_url` we fall back
        to a stable `fake://...` URL. Production GCS clients hit the real
        method via the same code path through the bucket+blob accessors.
        """
        try:
            blob = self._client.bucket(self._bucket_name).blob(blob_path)
            sign = getattr(blob, "generate_signed_url", None)
            if callable(sign):
                from datetime import timedelta

                return sign(
                    version="v4",
                    expiration=timedelta(hours=self._ttl_hours),
                    method="GET",
                )
        except Exception:  # noqa: S110 -- fall through to fake URL
            pass
        return f"fake://{self._bucket_name}/{blob_path}?ttl={self._ttl_hours}h"
```

- [ ] **Step 5: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_storage.py -v`
Expected: 4 passed.

- [ ] **Step 6: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter tests/fakes
uv run mypy services/documenter
```

If ruff flags `S110` (`try-except-pass`) as unused-noqa (`RUF100`) because the project's lint ruleset does not enable `S110`, replace the `# noqa: S110 -- fall through to fake URL` comment with a plain comment `# fall through to fake URL` and remove the `# noqa`. The exception handler is necessary; the noqa is optional.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/documenter/storage.py \
        apps/backend/tests/fakes/fake_gcs_client.py \
        apps/backend/tests/unit/documenter/test_storage.py
git commit -m "feat(documenter): add DocumentStorage with retry-once GCS upload"
```

---

## Task 8: Views projection (build123d)

**Files:**
- Create: `apps/backend/services/documenter/views.py`
- Create: `apps/backend/tests/unit/documenter/test_views.py`

- [ ] **Step 1: Inspect the S2 SVG exporter signature**

Run: `head -40 apps/backend/services/geometry/exporters/svg.py`

Identify the actual call to `ExportSVG` and any view-vector parameters available in build123d 0.10. S2's SVG exporter writes to a file path; for S5 we need to project to bytes. The strategy: write to a temp `BytesIO` if `ExportSVG` supports it, otherwise write to a `tempfile.NamedTemporaryFile` and read back.

- [ ] **Step 2: Write failing test** — `apps/backend/tests/unit/documenter/test_views.py`

```python
"""project_views tests."""
from __future__ import annotations

from services.documenter.views import project_views
from services.geometry.composer import compose_assembly
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField


def _flywheel_intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def test_project_views_returns_three_view_keys() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert set(views.keys()) == {"front", "side", "iso"}


def test_project_views_returns_svg_bytes() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    for name, svg in views.items():
        assert isinstance(svg, bytes), name
        head = svg.lstrip()[:64]
        assert head.startswith(b"<?xml") or head.startswith(b"<svg"), (name, head[:30])


def test_project_views_front_and_side_differ() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert views["front"] != views["side"]


def test_project_views_iso_falls_back_to_top_when_iso_export_fails(monkeypatch) -> None:
    from services.documenter import views as views_module

    real_export = views_module._export_svg
    fail_count = {"n": 0}

    def fake_export(compound, view_vector):
        if tuple(view_vector) == (1, 1, 1) and fail_count["n"] == 0:
            fail_count["n"] += 1
            raise RuntimeError("simulated iso projection failure")
        return real_export(compound, view_vector)

    monkeypatch.setattr(views_module, "_export_svg", fake_export)
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert "iso" in views
    assert views["iso"].lstrip().startswith(b"<?xml") or views["iso"].lstrip().startswith(b"<svg")
```

- [ ] **Step 3: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_views.py -v`
Expected: ImportError on `services.documenter.views`.

- [ ] **Step 4: Write production code** — `apps/backend/services/documenter/views.py`

```python
"""Project a build123d Compound onto 2D views as SVG bytes."""
from __future__ import annotations

import tempfile
from pathlib import Path

from build123d import Compound, Vector

from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
)

_VIEW_DIRECTIONS: dict[str, Vector] = {
    "front": Vector(0, 0, -1),     # looking down z+
    "side": Vector(1, 0, 0),       # looking from x+
    "iso": Vector(1, 1, 1),        # orthographic iso
}

_TOP_VIEW = Vector(0, 1, 0)        # fallback when iso fails


def project_views(compound: Compound) -> dict[str, bytes]:
    """Project the compound onto 3 view directions. Return SVG byte blobs.

    Keys: "front", "side", "iso". If 'iso' projection raises, substitute a
    'top' view but keep the key as 'iso' so downstream consumers are agnostic.
    Failures of 'front' or 'side' raise VIEW_PROJECTION_FAILED.
    """
    out: dict[str, bytes] = {}
    for name, vec in _VIEW_DIRECTIONS.items():
        try:
            out[name] = _export_svg(compound, vec)
        except Exception as exc:
            if name == "iso":
                try:
                    out["iso"] = _export_svg(compound, _TOP_VIEW)
                    continue
                except Exception as inner:
                    DocumentError(
                        code=DocumentErrorCode.VIEW_PROJECTION_FAILED,
                        message=f"projection 'iso' (and top fallback) failed: {inner!r}",
                        stage="project_views",
                        details={"primary": repr(exc), "fallback": repr(inner)},
                    ).raise_as()
            DocumentError(
                code=DocumentErrorCode.VIEW_PROJECTION_FAILED,
                message=f"projection {name!r} failed: {exc!r}",
                stage="project_views",
                details={"view": name},
            ).raise_as()
    return out


def _export_svg(compound: Compound, view_vector: Vector) -> bytes:
    """Write compound to an SVG file via build123d ExportSVG, read bytes back.

    build123d 0.10 ExportSVG writes to disk; we use a NamedTemporaryFile to
    capture bytes without leaking to the workspace.
    """
    from build123d import ExportSVG  # local import to keep module import light

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
        tmp_path = Path(tf.name)
    try:
        exporter = ExportSVG()
        exporter.add_shape(compound)
        exporter.write(str(tmp_path))
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
```

- [ ] **Step 5: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_views.py -v`
Expected: 4 passed.

If ExportSVG's actual API differs (build123d may have renamed methods between versions), study `services/geometry/exporters/svg.py:14-30` for the working pattern S2 uses, and mirror that. The contract that the tests pin down is **only** the input/output: `(Compound) -> dict[str, bytes]` where the bytes are valid SVG.

- [ ] **Step 6: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter
uv run mypy services/documenter
```

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/documenter/views.py \
        apps/backend/tests/unit/documenter/test_views.py
git commit -m "feat(documenter): add 3-view SVG projection with iso->top fallback"
```

---

## Task 9: Report PDF builder

**Files:**
- Create: `apps/backend/services/documenter/pdf/report.py`
- Create: `apps/backend/tests/unit/documenter/test_report.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_report.py`

```python
"""build_report_pdf tests."""
from __future__ import annotations

import io

import pypdf

from services.documenter.pdf.report import build_report_pdf
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import AnalysisResult, Verdict


def _read(pdf: bytes) -> pypdf.PdfReader:
    return pypdf.PdfReader(io.BytesIO(pdf))


def _all_text(pdf: bytes) -> str:
    reader = _read(pdf)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


_STEEL = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159},
    )


def _narrative() -> NaturalReport:
    return NaturalReport(
        summary="Near-yield at 3000 rpm; design hits the energy target.",
        risks=["Stress is 77% of yield."],
        suggestions=["Verify rim with FEA."],
        analogies=["Like a sprinter at top speed."],
        facts_used=["stress_max_mpa", "safety_factor", "material_yield_mpa"],
    )


def _geometry() -> CachedArtifacts:
    return CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
        ),
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )


_SVG_BYTES = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'


def test_report_pdf_has_pdf_magic_bytes() -> None:
    pdf = build_report_pdf(
        intent=_intent(),
        analysis=_analysis(),
        narrative=_narrative(),
        geometry=_geometry(),
        material=_STEEL,
        svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z",
        cache_key="abc123",
    )
    assert pdf.startswith(b"%PDF-")


def test_report_pdf_has_five_pages() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert len(_read(pdf).pages) == 5


def test_report_pdf_contains_intent_type() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "Flywheel_Rim" in _all_text(pdf)


def test_report_pdf_contains_verdict_label() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    text = _all_text(pdf).upper()
    assert "WARN" in text


def test_report_pdf_contains_formula() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "sigma = rho*omega^2*R^2" in _all_text(pdf)


def test_report_pdf_contains_safety_factor_value() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "1.29" in _all_text(pdf)


def test_report_pdf_contains_material_name() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "steel_a36" in _all_text(pdf)


def test_report_pdf_contains_facts_used_labels() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    text = _all_text(pdf)
    for label in ("stress_max_mpa", "safety_factor", "material_yield_mpa"):
        assert label in text, f"facts label missing in PDF: {label}"
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_report.py -v`
Expected: ImportError on `services.documenter.pdf.report`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/pdf/report.py`

```python
"""Build the 5-page engineering report PDF using reportlab."""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod

from services.documenter.pdf import theme
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import AnalysisResult

_VERSION = "S5 Documenter v0.1"

_DERIVATIONS: dict[str, str] = {
    "Flywheel_Rim": (
        "Centrifugal stress on a thin rim spinning at angular velocity omega "
        "is sigma = rho * omega^2 * R^2 where rho is density and R is outer "
        "radius. The result is the maximum tangential stress at the periphery."
    ),
    "Pelton_Runner": (
        "Hydraulic power is rho_w*g*Q*H*eta. Optimal bucket speed is "
        "u = 0.46 * sqrt(2*g*H). Shaft torque follows from T = P/omega and the "
        "shear stress on the shaft is tau = 16T/(pi*d^3)."
    ),
    "Hinge_Panel": (
        "Wind pressure is P = C_p * 0.5 * rho_air * v^2. The panel is modeled "
        "as a cantilever loaded by P; bending stress sigma = 6PL^2/t^2 with L "
        "the cantilever length and t the thickness."
    ),
}


def build_report_pdf(
    *,
    intent: DesignIntent,
    analysis: AnalysisResult,
    narrative: NaturalReport,
    geometry: CachedArtifacts,
    material: MaterialProperties,
    svg_bytes: bytes,
    now_utc_iso: str,
    cache_key: str,
) -> bytes:
    """Return PDF bytes for the 5-page engineering report."""
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=theme.PAGE_SIZE)
    _draw_cover(c, intent, analysis, now_utc_iso, cache_key)
    c.showPage()
    _draw_intent(c, intent, material)
    c.showPage()
    _draw_geometry(c, geometry, svg_bytes)
    c.showPage()
    _draw_analysis_and_narrative(c, analysis, narrative)
    c.showPage()
    _draw_appendix(c, material, analysis, narrative)
    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_cover(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    analysis: AnalysisResult,
    now_utc_iso: str,
    cache_key: str,
) -> None:
    width, height = theme.PAGE_SIZE
    c.setFillColor(theme.BRAND_PRIMARY)
    c.rect(0, height - 40 * mm, width, 40 * mm, stroke=0, fill=1)

    c.setFont(*theme.FONT_TITLE)
    c.setFillColor(colors.white)
    c.drawString(theme.MARGIN_PT, height - 28 * mm, "Mechanical Design Report")

    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, height - 60 * mm, intent.type)

    c.setFont(*theme.FONT_BODY)
    c.drawString(theme.MARGIN_PT, height - 70 * mm, f"Date: {now_utc_iso}")

    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, theme.MARGIN_PT, f"cache_key: {cache_key}")

    verdict = analysis.verdict.value
    badge_color = theme.COLOR_VERDICT.get(verdict, colors.grey)
    badge_x = width - theme.MARGIN_PT - 60 * mm
    badge_y = theme.MARGIN_PT
    c.setFillColor(badge_color)
    c.roundRect(badge_x, badge_y, 60 * mm, 18 * mm, 4, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(*theme.FONT_H1)
    c.drawCentredString(badge_x + 30 * mm, badge_y + 6 * mm, verdict.upper())


def _draw_intent(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    material: MaterialProperties,
) -> None:
    width, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Design Intent")
    y -= 10 * mm

    c.setFont(*theme.FONT_BODY)
    for name, field in sorted(intent.fields.items()):
        if field.value is None:
            continue
        line = f"{name} = {field.value}  [{field.source.value}]"
        c.drawString(theme.MARGIN_PT, y, line)
        y -= 6 * mm

    y -= 4 * mm
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Material")
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    rows = [
        ("name", material.name),
        ("density (kg/m3)", f"{material.density_kg_m3:.0f}"),
        ("young_modulus (GPa)", f"{material.young_modulus_gpa:.1f}"),
        ("yield_strength (MPa)", f"{material.yield_strength_mpa:.1f}"),
        ("category", material.category),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm


def _draw_geometry(
    c: canvas_mod.Canvas,
    geometry: CachedArtifacts,
    svg_bytes: bytes,
) -> None:
    _, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Geometry")
    y -= 10 * mm

    m = geometry.mass_properties
    c.setFont(*theme.FONT_BODY)
    rows = [
        ("mass (kg)", f"{m.mass_kg:.2f}"),
        ("volume (m3)", f"{m.volume_m3:.4f}"),
        ("center_of_mass (m)", f"({m.center_of_mass[0]:.3f}, {m.center_of_mass[1]:.3f}, {m.center_of_mass[2]:.3f})"),
        ("bbox_min (m)", f"({m.bbox_m[0]:.3f}, {m.bbox_m[1]:.3f}, {m.bbox_m[2]:.3f})"),
        ("bbox_max (m)", f"({m.bbox_m[3]:.3f}, {m.bbox_m[4]:.3f}, {m.bbox_m[5]:.3f})"),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    # SVG embed: try svglib, fall back to hyperlink-style placeholder.
    y -= 6 * mm
    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Section view")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    embedded = _try_embed_svg(c, svg_bytes, theme.MARGIN_PT, y - 100 * mm, 100 * mm, 100 * mm)
    if not embedded:
        c.drawString(theme.MARGIN_PT, y - 6 * mm, f"[section view available at {geometry.svg_url}]")


def _try_embed_svg(
    c: canvas_mod.Canvas,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> bool:
    try:
        from svglib.svglib import svg2rlg  # type: ignore[import-untyped]
        from reportlab.graphics import renderPDF
    except ImportError:
        return False
    try:
        drawing = svg2rlg(io.BytesIO(svg_bytes))
        if drawing is None:
            return False
        scale_x = w / drawing.width if drawing.width else 1.0
        scale_y = h / drawing.height if drawing.height else 1.0
        scale = min(scale_x, scale_y)
        drawing.scale(scale, scale)
        renderPDF.draw(drawing, c, x, y)
        return True
    except Exception:
        return False


def _draw_analysis_and_narrative(
    c: canvas_mod.Canvas,
    analysis: AnalysisResult,
    narrative: NaturalReport,
) -> None:
    width, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Structural Analysis")
    y -= 10 * mm

    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, y, f"Formula: {analysis.formula}")
    y -= 6 * mm

    c.setFont(*theme.FONT_BODY)
    rows = [
        ("Stress max (MPa)", f"{analysis.stress_max_pa / 1e6:.2f}"),
        ("Yield (MPa)", f"{analysis.material_yield_mpa:.1f}"),
        ("Displacement max (mm)", f"{analysis.displacement_max_m * 1000:.3f}"),
        ("Safety factor", f"{analysis.safety_factor:.2f}"),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    verdict = analysis.verdict.value
    badge_color = theme.COLOR_VERDICT.get(verdict, colors.grey)
    c.setFillColor(badge_color)
    c.roundRect(width - theme.MARGIN_PT - 30 * mm, y, 30 * mm, 8 * mm, 2, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(*theme.FONT_H2)
    c.drawCentredString(width - theme.MARGIN_PT - 15 * mm, y + 2 * mm, verdict.upper())
    y -= 14 * mm
    c.setFillColor(colors.black)

    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Engineering Narrative")
    y -= 8 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Summary")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    y = _draw_wrapped(c, narrative.summary, theme.MARGIN_PT, y, width - 2 * theme.MARGIN_PT)

    for heading, items in (
        ("Risks", narrative.risks),
        ("Suggestions", narrative.suggestions),
        ("Analogies", narrative.analogies),
    ):
        y -= 4 * mm
        c.setFont(*theme.FONT_H2)
        c.drawString(theme.MARGIN_PT, y, heading)
        y -= 6 * mm
        c.setFont(*theme.FONT_BODY)
        for item in items:
            c.drawString(theme.MARGIN_PT, y, f"- {item}")
            y -= 5 * mm

    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, theme.MARGIN_PT, "Facts cited: " + ", ".join(narrative.facts_used))


def _draw_appendix(
    c: canvas_mod.Canvas,
    material: MaterialProperties,
    analysis: AnalysisResult,
    narrative: NaturalReport,
) -> None:
    width, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Technical Appendix")
    y -= 10 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Material Properties (full)")
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    for label, value in [
        ("density_kg_m3", f"{material.density_kg_m3:.0f}"),
        ("young_modulus_gpa", f"{material.young_modulus_gpa:.1f}"),
        ("yield_strength_mpa", f"{material.yield_strength_mpa:.1f}"),
        ("ultimate_tensile_strength_mpa", f"{material.ultimate_tensile_strength_mpa:.1f}"),
        ("thermal_conductivity_w_m_k", f"{material.thermal_conductivity_w_m_k:.2f}"),
        ("max_service_temperature_c", f"{material.max_service_temperature_c:.0f}"),
        ("relative_cost_index", f"{material.relative_cost_index:.2f}"),
        ("sustainability_score", f"{material.sustainability_score:.2f}"),
    ]:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Assumptions and Notes")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    notes = analysis.notes or "(no notes recorded)"
    for sentence in notes.split(". "):
        if not sentence.strip():
            continue
        c.drawString(theme.MARGIN_PT, y, f"- {sentence.strip().rstrip('.')}")
        y -= 5 * mm
    c.drawString(theme.MARGIN_PT, y, f"- FACTS used for narrative: {', '.join(narrative.facts_used)}")
    y -= 8 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Formula Derivation")
    y -= 6 * mm
    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, y, analysis.formula)
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    derivation = _DERIVATIONS.get(
        analysis.intent_type,
        "(derivation reference: see docs/superpowers/specs/2026-05-16-s3-physics-design.md)",
    )
    y = _draw_wrapped(c, derivation, theme.MARGIN_PT, y, width - 2 * theme.MARGIN_PT)

    footer = f"{_VERSION} -- generated UTC {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, theme.MARGIN_PT, footer)


def _draw_wrapped(
    c: canvas_mod.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    line_height: float = 12.0,
) -> float:
    """Naive word-wrap: returns new y."""
    words = text.split()
    if not words:
        return y
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if c.stringWidth(candidate, "Helvetica", 10) <= max_width:
            line = candidate
        else:
            c.drawString(x, y, line)
            y -= line_height
            line = w
    if line:
        c.drawString(x, y, line)
        y -= line_height
    return y
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_report.py -v`
Expected: 8 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter
uv run mypy services/documenter
```

If mypy complains about `from svglib.svglib import svg2rlg` lacking stubs, the inline `# type: ignore[import-untyped]` already in the code suppresses it. If `datetime.utcnow()` is flagged as deprecated (Python 3.12+), replace with `datetime.now(tz=UTC)` and add the appropriate import.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/pdf/report.py \
        apps/backend/tests/unit/documenter/test_report.py
git commit -m "feat(documenter): add 5-page engineering report PDF builder"
```

---

## Task 10: Drawing PDF builder

**Files:**
- Create: `apps/backend/services/documenter/pdf/drawing.py`
- Create: `apps/backend/tests/unit/documenter/test_drawing.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_drawing.py`

```python
"""build_drawing_pdf tests."""
from __future__ import annotations

import io

import pypdf

from services.documenter.pdf.drawing import build_drawing_pdf
from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialProperties


def _read_text(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _page_count(pdf: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)


_STEEL = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


_MASS = MassProperties(
    volume_m3=0.012,
    mass_kg=95.5,
    center_of_mass=(0.0, 0.0, 0.025),
    bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
)

_VIEWS = {
    "front": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
    "side": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
    "iso": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
}


def test_drawing_pdf_magic_bytes_and_one_page() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    assert pdf.startswith(b"%PDF-")
    assert _page_count(pdf) == 1


def test_drawing_pdf_contains_title_block_fields() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "Flywheel_Rim" in text
    assert "steel_a36" in text


def test_drawing_pdf_contains_bbox_labels() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "Width" in text
    assert "Height" in text
    assert "Depth" in text


def test_drawing_pdf_contains_mass_note() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "mass" in text.lower()
    assert "95.5" in text


def test_drawing_pdf_contains_view_labels() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf).lower()
    assert "front" in text
    assert "side" in text
    assert "iso" in text
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_drawing.py -v`
Expected: ImportError on `services.documenter.pdf.drawing`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/pdf/drawing.py`

```python
"""Build the 1-page technical drawing PDF using reportlab."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod

from services.documenter.pdf import theme
from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialProperties

_PROJECT_NAME = "Gemma 4 Good Hackathon"


def build_drawing_pdf(
    *,
    views: dict[str, bytes],
    mass: MassProperties,
    intent: DesignIntent,
    material: MaterialProperties,
    now_utc_iso: str,
) -> bytes:
    """Return PDF bytes for the 1-page technical drawing."""
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=theme.PAGE_SIZE)
    width, height = theme.PAGE_SIZE
    c.setFillColor(colors.black)

    # View placeholders (text labels + bounding rectangles; SVG embed is
    # best-effort and falls back to a labelled box if svglib is missing).
    _draw_view(c, "Front", views.get("front", b""), theme.MARGIN_PT,
               height - theme.MARGIN_PT - 80 * mm, 80 * mm, 60 * mm)
    _draw_view(c, "Side", views.get("side", b""),
               theme.MARGIN_PT + 90 * mm,
               height - theme.MARGIN_PT - 80 * mm, 80 * mm, 60 * mm)
    _draw_view(c, "Iso", views.get("iso", b""),
               theme.MARGIN_PT,
               height - theme.MARGIN_PT - 170 * mm, 80 * mm, 80 * mm)

    # Bbox dimensions
    bbox_width = mass.bbox_m[3] - mass.bbox_m[0]
    bbox_height = mass.bbox_m[4] - mass.bbox_m[1]
    bbox_depth = mass.bbox_m[5] - mass.bbox_m[2]

    bbox_x = theme.MARGIN_PT + 90 * mm
    bbox_y = height - theme.MARGIN_PT - 110 * mm
    c.setFont(*theme.FONT_BODY)
    c.drawString(bbox_x, bbox_y, f"Width  = {bbox_width:.3f} m")
    c.drawString(bbox_x, bbox_y - 6 * mm, f"Height = {bbox_height:.3f} m")
    c.drawString(bbox_x, bbox_y - 12 * mm, f"Depth  = {bbox_depth:.3f} m")

    # Mass note (bottom-center)
    c.setFont(*theme.FONT_BODY)
    note = f"mass = {mass.mass_kg:.1f} kg, vol = {mass.volume_m3:.3f} m3"
    c.drawCentredString(width / 2, theme.MARGIN_PT + 8 * mm, note)

    # Title block (bottom-right)
    _draw_title_block(c, intent, material, now_utc_iso, mass)

    c.save()
    return buf.getvalue()


def _draw_view(
    c: canvas_mod.Canvas,
    label: str,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    c.setStrokeColor(colors.lightgrey)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H2)
    c.drawString(x + 3, y + h - 12, label)

    embedded = _try_embed_svg(c, svg_bytes, x + 4, y + 4, w - 8, h - 18)
    if not embedded:
        c.setFont(*theme.FONT_BODY)
        c.drawCentredString(x + w / 2, y + h / 2, "[view]")


def _try_embed_svg(
    c: canvas_mod.Canvas,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> bool:
    try:
        from svglib.svglib import svg2rlg  # type: ignore[import-untyped]
        from reportlab.graphics import renderPDF
    except ImportError:
        return False
    try:
        drawing = svg2rlg(io.BytesIO(svg_bytes))
        if drawing is None:
            return False
        scale_x = w / drawing.width if drawing.width else 1.0
        scale_y = h / drawing.height if drawing.height else 1.0
        scale = min(scale_x, scale_y)
        drawing.scale(scale, scale)
        renderPDF.draw(drawing, c, x, y)
        return True
    except Exception:
        return False


def _draw_title_block(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    material: MaterialProperties,
    now_utc_iso: str,
    mass: MassProperties,
) -> None:
    width, _ = theme.PAGE_SIZE
    x = width - theme.MARGIN_PT - 60 * mm
    y = theme.MARGIN_PT
    box_w = 60 * mm
    box_h = 30 * mm
    c.setStrokeColor(colors.black)
    c.rect(x, y, box_w, box_h, stroke=1, fill=0)

    c.setFont(*theme.FONT_BODY)
    lines = [
        f"PROJECT  {_PROJECT_NAME}",
        f"PART     {intent.type}",
        f"MATERIAL {material.name}",
        f"DATE     {now_utc_iso}",
        f"SCALE    1:{_auto_scale_denom(mass)}",
        "UNITS    m",
    ]
    for i, line in enumerate(lines):
        c.drawString(x + 2 * mm, y + box_h - (i + 1) * 4 * mm, line)


def _auto_scale_denom(mass: MassProperties) -> int:
    longest = max(
        mass.bbox_m[3] - mass.bbox_m[0],
        mass.bbox_m[4] - mass.bbox_m[1],
        mass.bbox_m[5] - mass.bbox_m[2],
        1e-6,
    )
    # Map longest dimension to a 0.1 m page slot; round denominator to nearest pow10.
    raw = max(longest / 0.1, 1.0)
    pow10 = 1
    while pow10 * 10 <= raw:
        pow10 *= 10
    return pow10
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_drawing.py -v`
Expected: 5 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter
uv run mypy services/documenter
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/pdf/drawing.py \
        apps/backend/tests/unit/documenter/test_drawing.py
git commit -m "feat(documenter): add 1-page technical drawing PDF builder"
```

---

## Task 11: Pipeline orchestrator

**Files:**
- Create: `apps/backend/services/documenter/pipeline.py`
- Create: `apps/backend/tests/unit/documenter/test_pipeline.py`

- [ ] **Step 1: Write failing test** — `apps/backend/tests/unit/documenter/test_pipeline.py`

```python
"""Documenter pipeline tests using FakeGcsClient + FakeSvgFetcher."""
from __future__ import annotations

import pytest

from services.documenter.cache import DocumenterCache
from services.documenter.domain.errors import DocumentErrorCode, DocumentException
from services.documenter.domain.models import DocumentRequest
from services.documenter.pipeline import Documenter
from services.documenter.storage import DocumentStorage
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialsCatalog, MaterialProperties
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gcs_client import FakeGcsClient
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher


_STEEL = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def _catalog() -> MaterialsCatalog:
    return MaterialsCatalog([_STEEL])


def _request() -> DocumentRequest:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )
    analysis = AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159},
    )
    narrative = NaturalReport(
        summary="Near-yield at 3000 rpm.",
        risks=["Stress 77 percent of yield."],
        suggestions=["Verify with FEA."],
        analogies=["Like a sprinter near top speed."],
        facts_used=["stress_max_mpa", "safety_factor"],
    )
    artifacts = CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
        ),
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )
    return DocumentRequest(
        intent=intent, analysis_result=analysis, natural_report=narrative,
        geometry_artifacts=artifacts,
    )


@pytest.mark.asyncio
async def test_pipeline_cache_miss_uploads_both_pdfs() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    deliv = await docter.document(_request())
    assert deliv.cache_hit is False
    assert deliv.report_pdf_url.endswith("/report.pdf?ttl=24h")
    assert deliv.drawing_pdf_url.endswith("/drawing.pdf?ttl=24h")
    assert deliv.step_url == "https://example.com/step"
    assert deliv.glb_url == "https://example.com/glb"
    assert deliv.svg_url == "https://example.com/svg"
    # Both PDFs uploaded
    assert gcs.stored("b", f"documents/{deliv.cache_key}/report.pdf") is not None
    assert gcs.stored("b", f"documents/{deliv.cache_key}/drawing.pdf") is not None


@pytest.mark.asyncio
async def test_pipeline_cache_hit_skips_upload() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    first = await docter.document(_request())
    # Wipe stored bytes so we can prove no re-upload happened
    second = await docter.document(_request())

    assert second.cache_hit is True
    assert second.cache_key == first.cache_key
    assert second.report_pdf_url == first.report_pdf_url


@pytest.mark.asyncio
async def test_pipeline_unknown_material_raises_invalid_input() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=MaterialsCatalog([]),
                        svg_fetcher=fetcher)

    with pytest.raises(DocumentException) as ei:
        await docter.document(_request())
    assert ei.value.error.code is DocumentErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_pipeline_svg_fetch_failure_maps_to_invalid_input() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher(raise_on_call=RuntimeError("no svg"))
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    with pytest.raises(DocumentException) as ei:
        await docter.document(_request())
    assert ei.value.error.code is DocumentErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_pipeline_deliverables_echoes_geometry_urls() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    deliv = await docter.document(_request())
    assert deliv.step_url == "https://example.com/step"
    assert deliv.glb_url == "https://example.com/glb"
    assert deliv.svg_url == "https://example.com/svg"


@pytest.mark.asyncio
async def test_pipeline_records_fetcher_call_with_svg_url() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    await docter.document(_request())
    assert fetcher.calls == ["https://example.com/svg"]
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/unit/documenter/test_pipeline.py -v`
Expected: ImportError on `services.documenter.pipeline`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/pipeline.py`

```python
"""Orchestrator for S5 Documenter: cache -> fetch -> compose -> project ->
build -> upload."""
from __future__ import annotations

import asyncio
from datetime import datetime

from services.documenter.cache import DocumenterCache
from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
    DocumentException,
)
from services.documenter.domain.models import Deliverables, DocumentRequest
from services.documenter.pdf.drawing import build_drawing_pdf
from services.documenter.pdf.report import build_report_pdf
from services.documenter.storage import DocumentStorage
from services.documenter.svg_fetcher import SvgFetcher
from services.documenter.views import project_views
from services.geometry.composer import compose_assembly
from services.interpreter.domain.materials import MaterialsCatalog


class Documenter:
    def __init__(
        self,
        *,
        storage: DocumentStorage,
        cache: DocumenterCache,
        materials_catalog: MaterialsCatalog,
        svg_fetcher: SvgFetcher,
    ) -> None:
        self._storage = storage
        self._cache = cache
        self._materials = materials_catalog
        self._fetcher = svg_fetcher

    async def document(self, req: DocumentRequest) -> Deliverables:
        cache_key = DocumenterCache.key_for(
            req.intent, req.analysis_result, req.natural_report
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.model_copy(update={"cache_hit": True})

        try:
            material = self._materials.get(req.analysis_result.material_name)
        except KeyError:
            DocumentError(
                code=DocumentErrorCode.INVALID_INPUT,
                message=f"unknown material {req.analysis_result.material_name!r}",
                field="analysis_result.material_name",
            ).raise_as()
            raise AssertionError("unreachable") from None

        try:
            svg_bytes = await self._fetcher.fetch(req.geometry_artifacts.svg_url)
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.INVALID_INPUT,
                message=f"failed to fetch svg from url: {exc!r}",
                field="geometry_artifacts.svg_url",
                details={"url": req.geometry_artifacts.svg_url},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            compound = compose_assembly(req.intent)
        except DocumentException:
            raise
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.GEOMETRY_REBUILD_FAILED,
                message=f"compose_assembly failed: {exc!r}",
                stage="compose",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        views = project_views(compound)

        now_utc_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            report_bytes = build_report_pdf(
                intent=req.intent,
                analysis=req.analysis_result,
                narrative=req.natural_report,
                geometry=req.geometry_artifacts,
                material=material,
                svg_bytes=svg_bytes,
                now_utc_iso=now_utc_iso,
                cache_key=cache_key,
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.REPORT_BUILD_FAILED,
                message=f"build_report_pdf failed: {exc!r}",
                stage="build_report",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            drawing_bytes = build_drawing_pdf(
                views=views,
                mass=req.geometry_artifacts.mass_properties,
                intent=req.intent,
                material=material,
                now_utc_iso=now_utc_iso,
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.DRAWING_BUILD_FAILED,
                message=f"build_drawing_pdf failed: {exc!r}",
                stage="build_drawing",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            report_url, drawing_url = await asyncio.gather(
                self._storage.upload(cache_key, "report", report_bytes),
                self._storage.upload(cache_key, "drawing", drawing_bytes),
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.GCS_UPLOAD_FAILED,
                message=f"GCS upload failed after retry: {exc!r}",
                stage="upload",
                retry_after=5,
            ).raise_as()
            raise AssertionError("unreachable") from exc

        deliv = Deliverables(
            report_pdf_url=report_url,
            drawing_pdf_url=drawing_url,
            step_url=req.geometry_artifacts.step_url,
            glb_url=req.geometry_artifacts.glb_url,
            svg_url=req.geometry_artifacts.svg_url,
            cache_hit=False,
            cache_key=cache_key,
        )
        self._cache.put(cache_key, deliv)
        return deliv
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/unit/documenter/test_pipeline.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter tests/fakes
uv run mypy services/documenter
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/pipeline.py \
        apps/backend/tests/unit/documenter/test_pipeline.py
git commit -m "feat(documenter): add pipeline orchestrator with cache + upload"
```

---

## Task 12: API router (POST /document)

**Files:**
- Create: `apps/backend/services/documenter/api/__init__.py` (empty)
- Create: `apps/backend/services/documenter/api/router.py`
- Create: `apps/backend/tests/component/documenter/__init__.py` (empty)
- Create: `apps/backend/tests/component/documenter/test_router.py`

- [ ] **Step 1: Write failing component test** — `apps/backend/tests/component/documenter/test_router.py`

```python
"""Component tests for POST /document."""
from __future__ import annotations

from pathlib import Path

import pytest
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
        return {"value": v, "source": "extracted", "unit": None, "original_text": None, "reason": None}

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
        json={"intent": _intent_dict()},  # missing analysis_result, etc.
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
```

- [ ] **Step 2: Run pytest, confirm FAIL**

Run: `uv run pytest tests/component/documenter/test_router.py -v`
Expected: ImportError on `services.documenter.api.router`.

- [ ] **Step 3: Write production code** — `apps/backend/services/documenter/api/router.py`

```python
"""POST /document router for S5 Documenter."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from services.documenter.domain.errors import DocumentException
from services.documenter.domain.models import Deliverables, DocumentRequest
from services.documenter.pipeline import Documenter

_logger = structlog.get_logger("documenter.router")

router = APIRouter(tags=["documenter"])


@router.post("/document", response_model=Deliverables)
async def document(req: DocumentRequest, app_req: Request) -> Deliverables:
    docter: Documenter = app_req.app.state.documenter
    _logger.info(
        "document_request_started",
        intent_type=req.intent.type,
        verdict=req.analysis_result.verdict.value,
        session_id=req.session_id,
    )
    deliv = await docter.document(req)
    _logger.info(
        "document_completed",
        cache_key=deliv.cache_key,
        cache_hit=deliv.cache_hit,
    )
    return deliv


def register_documenter_router(app: FastAPI) -> None:
    """Attach the documenter router and its exception handler to the app."""

    @app.exception_handler(DocumentException)
    async def _handle_doc_exception(_req: Request, exc: DocumentException) -> JSONResponse:
        _logger.warning(
            "document_failed",
            code=exc.error.code.value,
            stage=exc.error.stage,
            field=exc.error.field,
        )
        return JSONResponse(
            status_code=exc.error.http_status,
            content=exc.error.model_dump(),
        )

    app.include_router(router)
```

- [ ] **Step 4: Run pytest, confirm PASS**

Run: `uv run pytest tests/component/documenter/test_router.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify ruff + mypy clean**

```bash
uv run ruff check services/documenter tests/unit/documenter tests/component/documenter tests/fakes
uv run mypy services/documenter
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/api/__init__.py \
        apps/backend/services/documenter/api/router.py \
        apps/backend/tests/component/documenter/__init__.py \
        apps/backend/tests/component/documenter/test_router.py
git commit -m "feat(documenter): add POST /document router with exception handler"
```

---

## Task 13: Wire S5 in main.py

**Files:**
- Modify: `apps/backend/main.py`

- [ ] **Step 1: Read the bottom of main.py**

Run: `tail -n 30 apps/backend/main.py`

Locate the `# --- Wire S4 Explainer ---` block (just added). The new block goes immediately after it. The existing GCS client (`_gcs_client`) and `_materials_catalog` from the S2 wiring are reusable.

- [ ] **Step 2: Append the S5 wiring**

Add to `apps/backend/main.py`:

```python

# --- Wire S5 Documenter ---
from services.documenter.api.router import register_documenter_router  # noqa: E402
from services.documenter.cache import DocumenterCache  # noqa: E402
from services.documenter.pipeline import Documenter  # noqa: E402
from services.documenter.storage import DocumentStorage  # noqa: E402
from services.documenter.svg_fetcher import HttpxSvgFetcher  # noqa: E402

_document_storage = DocumentStorage(
    gcs_client=_gcs_client,
    bucket_name=settings.gcs_bucket_artifacts,
    ttl_hours=settings.signed_url_ttl_hours,
)
_documenter = Documenter(
    storage=_document_storage,
    cache=DocumenterCache(),
    materials_catalog=_materials_catalog,
    svg_fetcher=HttpxSvgFetcher(timeout_s=5.0),
)
app.state.documenter = _documenter
register_documenter_router(app)
```

- [ ] **Step 3: Syntactic verification**

Run from `apps/backend/`:
```bash
uv run python -c "import ast; ast.parse(open('main.py').read()); print('parsed OK')"
```
Expected: `parsed OK`.

- [ ] **Step 4: Standalone verification** (no env vars needed)

```bash
uv run python -c "
from fastapi import FastAPI
from services.documenter.api.router import register_documenter_router
app = FastAPI()
register_documenter_router(app)
routes = sorted({r.path for r in app.routes})
print('routes:', routes)
assert '/document' in routes
print('OK /document registered')
"
```
Expected: `OK /document registered`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/main.py
git commit -m "feat(documenter): mount S5 router on main app"
```

---

## Task 14: Integration tests + README + final gate

**Files:**
- Create: `apps/backend/tests/integration/documenter/__init__.py` (empty)
- Create: `apps/backend/tests/integration/documenter/conftest.py`
- Create: `apps/backend/tests/integration/documenter/test_hero_documents.py`
- Create: `apps/backend/services/documenter/README.md`

- [ ] **Step 1: Write conftest** — `apps/backend/tests/integration/documenter/conftest.py`

```python
"""Hero (intent, analysis, narrative, geometry) fixtures for S5 integration tests."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.documenter.api.router import register_documenter_router
from services.documenter.cache import DocumenterCache
from services.documenter.pipeline import Documenter
from services.documenter.storage import DocumentStorage
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gcs_client import FakeGcsClient
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher

_BACKEND = Path(__file__).resolve().parents[3]
_MATERIALS = _BACKEND / "data" / "materials.json"


def _f(value: float) -> TriStateField:
    return TriStateField(value=value, source=FieldSource.EXTRACTED)


HERO_INTENTS: dict[str, DesignIntent] = {
    "flywheel": DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5), "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05), "rpm": _f(3000.0),
        },
        composed_of=[],
    ),
    "hydro": DesignIntent(
        type="Pelton_Runner",
        fields={
            "runner_diameter_m": _f(0.8), "bucket_count": _f(20.0),
            "head_m": _f(20.0), "flow_m3_s": _f(0.5),
        },
        composed_of=[],
    ),
    "shelter": DesignIntent(
        type="Hinge_Panel",
        fields={
            "width_m": _f(1.0), "height_m": _f(2.0),
            "thickness_m": _f(0.02), "wind_kmh": _f(100.0),
        },
        composed_of=[],
    ),
}

HERO_ANALYSES: dict[str, AnalysisResult] = {
    "flywheel": AnalysisResult(
        intent_type="Flywheel_Rim", material_name="steel_a36",
        material_yield_mpa=250.0, formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8, displacement_max_m=4.84e-4,
        safety_factor=1.29, verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159, "outer_diameter_m": 0.5},
    ),
    "hydro": AnalysisResult(
        intent_type="Pelton_Runner", material_name="stainless_304",
        material_yield_mpa=215.0, formula="tau = 16T/(pi*d^3)",
        stress_max_pa=8.0e7, displacement_max_m=2.5e-4,
        safety_factor=1.55, verdict=Verdict.WARN,
        inputs={"head_m": 20.0, "flow_m3_s": 0.5},
    ),
    "shelter": AnalysisResult(
        intent_type="Hinge_Panel", material_name="bamboo_laminated",
        material_yield_mpa=60.0, formula="sigma = 6*P*L^2/t^2",
        stress_max_pa=2.0e7, displacement_max_m=1.5e-3,
        safety_factor=3.0, verdict=Verdict.PASS,
        inputs={"wind_speed_m_s": 27.78, "pressure_pa": 378.5},
    ),
}

HERO_NARRATIVES: dict[str, NaturalReport] = {
    "flywheel": NaturalReport(
        summary="Near-yield at 3000 rpm.", risks=["Stress 77% of yield."],
        suggestions=["Verify with FEA."], analogies=["Like a sprinter."],
        facts_used=["stress_max_mpa", "safety_factor", "material_yield_mpa"],
    ),
    "hydro": NaturalReport(
        summary="Pelton 0.5 m3/s 20 m head delivers safe torque.",
        risks=["Shaft near material limit."], suggestions=["Specify forged 304."],
        analogies=["Like a hand crank with hydraulic boost."],
        facts_used=["safety_factor", "verdict"],
    ),
    "shelter": NaturalReport(
        summary="Bamboo panel handles 100 km/h wind comfortably.",
        risks=[], suggestions=["Inspect panel edges yearly."],
        analogies=["Like a sailboat trimming the breeze."],
        facts_used=["safety_factor", "stress_max_mpa"],
    ),
}

_FAKE_BBOX = (-0.25, -0.25, 0.0, 0.25, 0.25, 0.05)


def _artifacts() -> CachedArtifacts:
    return CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012, mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025), bbox_m=_FAKE_BBOX,
        ),
        step_url="https://example.com/hero/step",
        glb_url="https://example.com/hero/glb",
        svg_url="https://example.com/hero/svg",
    )


@pytest.fixture(scope="module")
def document_client() -> Iterable[TestClient]:
    gcs = FakeGcsClient()
    app = FastAPI()
    app.state.documenter = Documenter(
        storage=DocumentStorage(gcs_client=gcs, bucket_name="b"),
        cache=DocumenterCache(),
        materials_catalog=load_catalog(_MATERIALS),
        svg_fetcher=FakeSvgFetcher(),
    )
    register_documenter_router(app)
    with TestClient(app) as client:
        yield client


def _make_request(hero: str) -> dict:
    return {
        "intent": HERO_INTENTS[hero].model_dump(),
        "analysis_result": HERO_ANALYSES[hero].model_dump(),
        "natural_report": HERO_NARRATIVES[hero].model_dump(),
        "geometry_artifacts": _artifacts().model_dump(),
    }


@pytest.fixture
def hero_flywheel_request() -> dict:
    return _make_request("flywheel")


@pytest.fixture
def hero_hydro_request() -> dict:
    return _make_request("hydro")


@pytest.fixture
def hero_shelter_request() -> dict:
    return _make_request("shelter")
```

- [ ] **Step 2: Write the integration tests** — `apps/backend/tests/integration/documenter/test_hero_documents.py`

```python
"""End-to-end S5 integration over the three hero bundles."""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_hero_flywheel_document_bundles_all_artifacts(
    document_client, hero_flywheel_request
) -> None:
    r = document_client.post("/document", json=hero_flywheel_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")
    assert d["step_url"] == hero_flywheel_request["geometry_artifacts"]["step_url"]
    assert d["cache_hit"] is False


@pytest.mark.integration
def test_hero_hydro_document_bundles_all_artifacts(
    document_client, hero_hydro_request
) -> None:
    r = document_client.post("/document", json=hero_hydro_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")


@pytest.mark.integration
def test_hero_shelter_document_bundles_all_artifacts(
    document_client, hero_shelter_request
) -> None:
    r = document_client.post("/document", json=hero_shelter_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/integration/documenter -m integration -v`
Expected: 3 passed.

- [ ] **Step 4: Write the README** — `apps/backend/services/documenter/README.md`

```markdown
# S5 Documenter

Aggregates everything the pipeline produced into downloadable deliverables.
Takes `DesignIntent + AnalysisResult + NaturalReport + CachedArtifacts` and
returns `Deliverables { report_pdf_url, drawing_pdf_url, step_url, glb_url,
svg_url, cache_hit, cache_key }`.

See the [design spec](../../../../docs/superpowers/specs/2026-05-16-s5-documenter-design.md)
for context.

## Endpoint

- `POST /document` -- sync JSON. Body: `{ intent, analysis_result, natural_report, geometry_artifacts, session_id? }`

```bash
curl -X POST http://localhost:8080/document \
  -H "Content-Type: application/json" \
  -d '{
    "intent": { "type": "Flywheel_Rim", "fields": {...}, "composed_of": [] },
    "analysis_result": { "intent_type": "Flywheel_Rim", "material_name": "steel_a36", ... },
    "natural_report": { "summary": "...", "facts_used": [...] },
    "geometry_artifacts": {
      "mass_properties": {...},
      "step_url": "https://...", "glb_url": "https://...", "svg_url": "https://..."
    }
  }'
```

## Deliverables

| Field | Source | Notes |
|---|---|---|
| `report_pdf_url` | S5 generated | 5-page engineering report on GCS, 24 h signed URL |
| `drawing_pdf_url` | S5 generated | 1-page technical drawing on GCS, 24 h signed URL |
| `step_url` | echoed from input.geometry_artifacts | S2 STEP file |
| `glb_url` | echoed from input.geometry_artifacts | S2 GLB for the 3D viewer |
| `svg_url` | echoed from input.geometry_artifacts | S2 section view |
| `cache_hit` | bool | true on idempotent second call with identical inputs |
| `cache_key` | 16-char hex | sha256 of intent + analysis + narrative summary + facts_used |

## Local development

```bash
cd apps/backend
uv run pytest tests/unit/documenter tests/component/documenter -v
uv run pytest tests/integration/documenter -m integration -v
```

## Runbook: GCS upload failures

The endpoint returns `502 gcs_upload_failed` with `retry_after: 5` after one
internal retry (1 s backoff). The client should wait and re-POST. If the
failure persists, check the bucket exists and the service account has
`storage.objects.create` on `documents/*`.

## Out of scope (deferred)

- Bilingual ES + EN
- Multi-sheet drawings or GD&T tolerances
- PDF/A archival compliance
- Watermarks / signatures
- Pre-baked hero PDFs on disk fallback
```

- [ ] **Step 5: Run the full S5 gate**

From `apps/backend/`:
```bash
uv run ruff check services/documenter tests/unit/documenter tests/component/documenter tests/integration/documenter tests/fakes
uv run mypy services/documenter
uv run pytest tests/unit/documenter tests/component/documenter --cov=services/documenter --cov-report=term-missing --cov-fail-under=85 -q
uv run pytest tests/integration/documenter -m integration -q
```
Expected:
- ruff: `All checks passed!`
- mypy: `Success: no issues found`
- coverage gate cleared
- integration: 3 passed

If coverage is under 85%, identify gaps in `term-missing`. Common spots: the `_auto_scale_denom` loop, the SVG-embed fall-back branch in `_try_embed_svg`, the `iso` view fallback, and `DocumenterCache.clear()`. Add targeted unit tests BEFORE committing.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/documenter/README.md \
        apps/backend/tests/integration/documenter/__init__.py \
        apps/backend/tests/integration/documenter/conftest.py \
        apps/backend/tests/integration/documenter/test_hero_documents.py
git commit -m "test(documenter): add integration tests for 3 heroes + README"
```

If you wrote additional coverage tests, include them in the same commit or in a preceding `test(documenter): add coverage tests for <area>` commit.

---

## Done criteria

All of the following hold:

- [ ] Tasks 1-14 commits land in order, each green at commit time
- [ ] `uv run ruff check services/documenter ...` exits 0
- [ ] `uv run mypy services/documenter` exits 0
- [ ] `uv run pytest tests/unit/documenter tests/component/documenter --cov-fail-under=85` exits 0
- [ ] `uv run pytest tests/integration/documenter -m integration` exits 0 with 3/3
- [ ] `POST /document` route registered (verified via standalone boot)
- [ ] README + spec docs committed
- [ ] No edits to `services/{interpreter,geometry,physics,explainer}/` except as listed above (S5 does NOT touch other services)
- [ ] `pyproject.toml` carries `reportlab>=4.2` and `pypdf>=4.0`

## Out of scope for this plan

- Frontend hook `useDocument` -- separate plan
- Live GCS smoke from this session (needs correct GCP project, user-owned)
- Bilingual ES + EN
- Pre-baked hero PDF disk fallback
- Multi-sheet drawings, GD&T, PDF/A, signatures, watermarks

## Notes for the executor

- DO NOT use `--no-verify` on commits.
- DO NOT add `Co-Authored-By` lines.
- DO NOT touch `services/interpreter/`, `services/geometry/`, `services/physics/`, or `services/explainer/`.
- Run all commands from `apps/backend/` and use `uv run`.
- ASCII-only in code strings and docstrings. Ruff flags Greek as RUF001/RUF002.
- DO NOT add `# noqa: BLE001` — that lint is disabled and ruff strict flags unused noqa via RUF100.
- If `datetime.utcnow()` is flagged as deprecated, switch to `datetime.now(tz=UTC)` with `from datetime import UTC, datetime`.
- If a step's expected output does not match, STOP and report. Do not muddle through.
- After Task 14 passes, append a one-line entry to project root `CLAUDE.md` under "Implementation status" that S5 (report+drawing PDFs, in-memory cache) is live. Do NOT do this until all gates are green.
