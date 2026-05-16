# S5 Documenter — Design Spec

**Date**: 2026-05-16
**Subsystem**: S5 — Documenter Service
**Parent document**: [DESIGN.md](../../../DESIGN.md)
**Depends on**: [S2 Geometry spec](2026-04-19-s2-geometry-design.md), [S3 Physics spec](2026-05-16-s3-physics-design.md), [S4 Explainer spec](2026-05-16-s4-explainer-design.md)
**Status**: Approved, ready for implementation plan

---

## 1. Context and Purpose

S5 Documenter is the final stage of the pipeline. It takes everything the other subsystems produced — the `DesignIntent` (S1), the `CachedArtifacts` with signed STEP/GLB/SVG URLs (S2), the `AnalysisResult` (S3), and the `NaturalReport` (S4) — and packages them into a downloadable professional bundle: a five-page engineering report PDF, a single-page technical drawing PDF, plus the existing CAD artifact URLs.

**Why this subsystem matters**: it is the deliverable. Everything before S5 is *process*; S5 is the artifact the user actually downloads, attaches to a tender, opens in a browser, or sends to a manufacturer. The hackathon rubric weighs Storytelling at 30 points and Technical Depth at 30 points — a polished PDF that cites real formulas and material properties is the single most visible piece of "this is real engineering" in the demo.

**Why the scope is two PDFs + URL passthrough**: STEP / GLB / SVG already live as 24-hour signed URLs on GCS thanks to S2. Re-generating them is waste. S5's value-add is the report PDF (combines mass + stress + narrative + appendix) and the drawing PDF (3 views + bounding box dimensions). Multi-sheet drawings, GD&T, PDF/A, digital signatures, bilingual reports — all explicitly deferred.

---

## 2. Scope and Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deliverables | **`report_pdf` (5 pages) + `drawing_pdf` (1 page) + passthrough S2 URLs** | Report tells the story; drawing supplies the CAD-style summary; existing STEP/GLB/SVG are echoed |
| API shape | **`POST /document` sync JSON** | PDFs are sub-second to build; no SSE, no async, no Cloud Tasks |
| Languages | **English only for MVP** | Bilingual deferred (S4 also English-only) |
| Storage | **GCS, same bucket as S2, under `documents/{cache_key}/` prefix** | Reuses the bucket + CORS already configured; clean namespace separation |
| Caching | **In-memory dict keyed by `sha256(intent + analysis + narrative)`** | PDFs are deterministic given identical inputs; replay during demo is free |
| Retry policy | **0 retries on build failures, 1 retry on GCS upload** | Build failures are deterministic; upload failures may be transient |
| Module layout | **`apps/backend/services/documenter/` sibling of `services/{interpreter,geometry,physics,explainer}/`** | Each subsystem replaceable per CLAUDE.md principle |
| PDF library | **`reportlab>=4.2`** added to `pyproject.toml` | Industry-standard, no system deps, deterministic output |
| PDF text extraction in tests | **`pypdf>=4.0`** added as `dev` dependency | Tests verify PDF invariants by extracting text |
| SVG embedding | **`svglib` if available; otherwise hyperlink placeholder** | Belt-and-braces — drawing still renders even when svglib breaks on build123d-emitted SVG |
| View projections | **build123d `ExportSVG` with three direction vectors (front, side, iso)** | Reuses existing geometry stack; if `iso` fails the system falls back to `top` view |
| Rate limit | **10 req/min per IP** | Heaviest endpoint (PDF build + 2 GCS uploads); mirrors S2 |
| Pre-baked disk fallback | **Out of scope for MVP** | Stretch goal only — `data/document_artifacts/{cache_key}/` |

---

## 3. Architecture

Five logical layers + a transversal cache.

```
HTTP Layer        POST /document (FastAPI sync JSON)
                  ├─ DTO validate (Pydantic)
                  └─ extract intent + analysis + narrative + geometry_artifacts

Views Layer       build123d Compound -> 3 SVG views (front, side, iso)
                  └─ views.py: project_views(compound) -> {front, side, iso} bytes

PDF Layer         reportlab document builders
                  ├─ pdf/report.py: 5-page engineering report
                  ├─ pdf/drawing.py: 1-page technical drawing
                  └─ pdf/theme.py: fonts, colors, page margins, brand constants

Storage Layer     GCS uploader + signed URLs (24 h TTL)
                  └─ storage.py: upload bytes -> gs://{bucket}/documents/{cache_key}/{name}.pdf

Cache Layer       In-memory dict
                  └─ cache.py: sha256(intent + analysis + narrative) -> Deliverables
```

### Layer responsibilities

**HTTP Layer** — FastAPI router that accepts `POST /document {intent, analysis_result, natural_report, geometry_artifacts, session_id?}` and returns `Deliverables` JSON. Pre-solve errors are 422; build failures 500; GCS upload failures 502 with `retry_after`.

**Views Layer** — `views.py:project_views(compound)` projects the build123d `Compound` (rebuilt from the intent via `compose_assembly`) onto three direction vectors and returns three SVG byte blobs. If the `iso` projection raises (build123d 0.10 limitation), the function silently substitutes a `top` view. Failures of all three projections raise `VIEW_PROJECTION_FAILED`.

**PDF Layer** — three modules. `theme.py` holds visual constants (colors, fonts, margins, verdict color map). `report.py:build_report_pdf(intent, analysis, narrative, geometry, material, svg_bytes)` returns the 5-page report PDF bytes. `drawing.py:build_drawing_pdf(views, mass, intent, material)` returns the 1-page drawing PDF bytes. Both are **pure functions** — no I/O, no globals.

**Storage Layer** — `storage.py:DocumentStorage` uploads bytes to `documents/{cache_key}/{name}.pdf`, signs a 24-hour URL, and retries once with 1-second backoff on transient GCS failures.

**Cache Layer** — `cache.py:DocumenterCache` is a thin wrapper around a dict. The key includes intent values, analysis numbers, verdict, material name, narrative `facts_used` (sorted), and an 8-character hash of `narrative.summary` to disambiguate retry-path LLM outputs.

### Key design principle

**Reuse the URLs we already have.** S5 is an aggregator, not a re-generator. STEP / GLB / SVG live as signed URLs on S2's bucket — S5 echoes them in the `Deliverables` payload. The only bytes S5 itself creates are the two PDFs. This keeps the implementation thin and makes the cache key small.

---

## 4. Components

### 4.1 Domain Models

`services/documenter/domain/models.py`:

```python
from pydantic import BaseModel

from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class DocumentRequest(BaseModel):
    intent: DesignIntent
    analysis_result: AnalysisResult
    natural_report: NaturalReport
    geometry_artifacts: CachedArtifacts
    session_id: str | None = None


class Deliverables(BaseModel):
    report_pdf_url: str
    drawing_pdf_url: str
    step_url: str             # echo from input.geometry_artifacts.step_url
    glb_url: str              # echo from input.geometry_artifacts.glb_url
    svg_url: str              # echo from input.geometry_artifacts.svg_url
    cache_hit: bool
    cache_key: str
```

### 4.2 Error Taxonomy

`services/documenter/domain/errors.py`:

```python
class DocumentErrorCode(StrEnum):
    INVALID_INPUT          = "invalid_input"            # 422
    GEOMETRY_REBUILD_FAILED = "geometry_rebuild_failed" # 500
    VIEW_PROJECTION_FAILED  = "view_projection_failed"  # 500
    REPORT_BUILD_FAILED    = "report_build_failed"      # 500
    DRAWING_BUILD_FAILED   = "drawing_build_failed"     # 500
    GCS_UPLOAD_FAILED      = "gcs_upload_failed"        # 502, retry_after=5
    INTERNAL_ERROR         = "internal_error"           # 500


class DocumentError(BaseModel):
    code: DocumentErrorCode
    message: str
    field: str | None = None
    stage: str | None = None
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int: ...

    def raise_as(self) -> None: ...


class DocumentException(RuntimeError):  # noqa: N818 -- intentional
    def __init__(self, error: DocumentError) -> None: ...
```

### 4.3 Theme

`services/documenter/pdf/theme.py`:

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

PAGE_SIZE = A4                                    # (595.27, 841.89) pt
MARGIN_PT = 50                                    # ~18 mm

BRAND_PRIMARY = colors.HexColor("#1A73E8")
BRAND_ACCENT  = colors.HexColor("#34A853")
COLOR_VERDICT = {
    "pass": colors.HexColor("#34A853"),
    "warn": colors.HexColor("#F4B400"),
    "fail": colors.HexColor("#DB4437"),
}

FONT_TITLE = ("Helvetica-Bold", 22)
FONT_H1    = ("Helvetica-Bold", 14)
FONT_H2    = ("Helvetica-Bold", 11)
FONT_BODY  = ("Helvetica", 10)
FONT_MONO  = ("Courier", 9)
```

### 4.4 Report PDF (`pdf/report.py`)

Five page builders, each a pure helper called by a top-level `build_report_pdf`. Layout below describes content; reportlab implementation detail is the executor's job.

```
Page 1 — COVER
  BRAND_PRIMARY band, 40 mm tall, top of page
  TITLE      "Mechanical Design Report"
  SUBTITLE   intent.type
  DATE       ISO date (today, UTC)
  CACHE_KEY  16-char hex (small monospace footer)
  VERDICT BADGE (color from COLOR_VERDICT), rounded rect bottom-right

Page 2 — DESIGN INTENT
  H1  "Design Intent"
  TABLE: every intent.fields entry (Field | Value | Source-chip)
         source rendered as small chip: extracted / defaulted / missing
  H2  "Material"
  TABLE: name / density_kg_m3 / young_modulus_gpa / yield_strength_mpa / category

Page 3 — GEOMETRY
  H1  "Geometry"
  TABLE: mass_kg / volume_m3 / center_of_mass / bbox_min / bbox_max
  FIG: section SVG from input.geometry_artifacts.svg_url
       scaled to fit 100x100 mm box; if svglib fails -> placeholder text
       "[section view available at svg_url]"

Page 4 — ANALYSIS + NARRATIVE
  H1  "Structural Analysis"
  KV-row: Formula     = analysis.formula (mono)
  KV-row: Stress max  = {stress_max_pa/1e6:.2f} MPa
  KV-row: Yield       = {material.yield_strength_mpa:.1f} MPa
  KV-row: Displacement max = {displacement_max_m*1000:.3f} mm
  KV-row: Safety factor = {safety_factor:.2f}  [VERDICT BADGE]
  H1  "Engineering Narrative"
  H2  "Summary"      ->  narrative.summary (Paragraph wrap)
  H2  "Risks"        ->  bullets
  H2  "Suggestions"  ->  bullets
  H2  "Analogies"    ->  bullets
  FOOTER small: "Facts cited: " + ", ".join(narrative.facts_used)

Page 5 — TECHNICAL APPENDIX
  H1  "Technical Appendix"
  H2  "Material Properties (full)"
    TABLE: density / E / yield / UTS / k / T_max / cost_index / sustainability
  H2  "Assumptions and Notes"
    BULLETS: analysis.notes split by sentence + "FACTS used for narrative" line
  H2  "Formula Derivation"
    MONO block: analysis.formula
    PROSE: short canned derivation text per intent.type from a lookup table;
           if unknown intent.type, "(derivation reference: see docs/.../s3-physics)"
  FOOTER: "S5 Documenter v0.1 -- generated UTC YYYY-MM-DD HH:MM"
```

**Function signature**:

```python
def build_report_pdf(
    intent: DesignIntent,
    analysis: AnalysisResult,
    narrative: NaturalReport,
    geometry: CachedArtifacts,
    material: MaterialProperties,
    svg_bytes: bytes,
    *,
    now_utc_iso: str,
    cache_key: str,
) -> bytes:
    """Return PDF bytes for the 5-page engineering report."""
```

Pure function; tests can call directly with synthetic data.

### 4.5 Drawing PDF (`pdf/drawing.py`)

One-page technical drawing.

```
Page 1 — TECHNICAL DRAWING
  TITLE BLOCK (bottom-right, 60x30 mm box with border)
    PROJECT  "Gemma 4 Good Hackathon"
    PART     intent.type
    MATERIAL material.name
    DATE     ISO
    SCALE    auto: 1:N where N = round-to-pow10(max(bbox dimensions) / 0.1 m)
    UNITS    "m"

  THREE VIEWS arranged:
    Front (xy plane, looking down z+)  top-left      ~80x60 mm
    Side  (yz plane, looking down x+)  top-right     ~80x60 mm
    Iso   (orthographic)               bottom-left   ~80x80 mm
    (if iso failed, label is "Top" and SVG is the top-view substitute)

  BBOX DIMENSIONS overlaid as text labels:
    "Width  = {bbox_max_x - bbox_min_x:.3f} m"
    "Height = {bbox_max_y - bbox_min_y:.3f} m"
    "Depth  = {bbox_max_z - bbox_min_z:.3f} m"

  MASS NOTE (bottom-center, small): "mass = {mass_kg:.1f} kg, vol = {volume_m3:.3f} m³"
```

**Function signature**:

```python
def build_drawing_pdf(
    views: dict[str, bytes],            # {'front': svg, 'side': svg, 'iso': svg}
    mass: MassProperties,
    intent: DesignIntent,
    material: MaterialProperties,
    *,
    now_utc_iso: str,
) -> bytes:
    """Return PDF bytes for the 1-page technical drawing."""
```

### 4.6 Views Projection

`services/documenter/views.py`:

```python
from build123d import Compound, Vector

_VIEW_DIRECTIONS = {
    "front": Vector(0, 0, -1),    # looking down z
    "side":  Vector(1, 0, 0),     # looking from x+
    "iso":   Vector(1, 1, 1),     # 1,1,1 orthographic
}

def project_views(compound: Compound) -> dict[str, bytes]:
    """Project the compound onto 3 view directions, return SVG byte blobs.

    If 'iso' raises, substitute a 'top' view (Vector(0, 1, 0)) and report
    that key as 'iso' anyway (downstream UI is agnostic).
    """
    out: dict[str, bytes] = {}
    for name, vec in _VIEW_DIRECTIONS.items():
        try:
            out[name] = _export_svg(compound, view_vector=vec)
        except Exception as exc:
            if name == "iso":
                out["iso"] = _export_svg(compound, view_vector=Vector(0, 1, 0))
            else:
                raise DocumentError(
                    code=VIEW_PROJECTION_FAILED,
                    message=f"projection {name!r} failed: {exc!r}",
                    stage="project_views",
                ).raise_as()
    return out
```

The internal `_export_svg` helper wraps build123d `ExportSVG` so tests can monkey-patch it.

### 4.7 Storage

`services/documenter/storage.py`:

```python
class DocumentStorage:
    def __init__(
        self,
        gcs_client: Any,
        bucket_name: str,
        ttl_hours: int = 24,
        *,
        prefix: str = "documents",
    ) -> None: ...

    async def upload(
        self,
        cache_key: str,
        name: str,                            # "report" or "drawing"
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload to documents/{cache_key}/{name}.pdf. Return signed URL.

        One retry with 1-second backoff on transient google.api_core errors.
        """
```

Reuses the same signed-URL signing pattern as `services/geometry/cache.GcsGeometryCache._signed_url` (v4 signing with credential fallback for local dev). A `FakeGcsClient` test double covers the upload path without hitting GCS.

### 4.8 Cache

`services/documenter/cache.py`:

```python
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
                k: f.value for k, f in sorted(intent.fields.items())
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

    def get(self, key: str) -> Deliverables | None: ...
    def put(self, key: str, value: Deliverables) -> None: ...
    def clear(self) -> None: ...
```

`summary_hash` (8 chars) is included so two NaturalReports with the same `facts_used` but different prose produce different document caches — important when S4's retry path yields a different summary.

### 4.9 SVG Fetcher

`services/documenter/svg_fetcher.py`:

```python
class SvgFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class HttpxSvgFetcher:
    """Production fetcher using httpx (already a backend dep)."""

    def __init__(self, timeout_s: float = 5.0) -> None: ...

    async def fetch(self, url: str) -> bytes: ...
```

Tests use `FakeSvgFetcher` returning canned SVG bytes.

### 4.10 Pipeline

`services/documenter/pipeline.py`:

```python
class Documenter:
    def __init__(
        self,
        *,
        storage: DocumentStorage,
        cache: DocumenterCache,
        materials_catalog: MaterialsCatalog,
        svg_fetcher: SvgFetcher,
    ) -> None: ...

    async def document(self, req: DocumentRequest) -> Deliverables:
        """Cache lookup -> fetch SVG -> compose -> project -> 2 PDF builds ->
        2 parallel GCS uploads -> cache.put -> return Deliverables.
        """
```

### 4.11 API Router

`services/documenter/api/router.py`:

```python
@router.post("/document", response_model=Deliverables)
async def document(req: DocumentRequest, app_req: Request) -> Deliverables:
    docter: Documenter = app_req.app.state.documenter
    return await docter.document(req)
```

`register_documenter_router(app)` mounts the route and attaches an exception handler that maps `DocumentException` to the matching HTTP status with the structured error body.

---

## 5. Data Flow

### 5.1 Happy path — cache miss (~600 ms - 2 s)

```
POST /document {intent, analysis_result, natural_report, geometry_artifacts}
  -> Pydantic validate                                    [422 invalid_input]
  -> compute cache_key = sha256(intent + analysis + narrative)
  -> cache.get(key) is None
  -> material = catalog.get(analysis.material_name)       [422 invalid_input if missing]
  -> svg_bytes = svg_fetcher.fetch(geometry_artifacts.svg_url)
                                                          [422 invalid_input if 4xx; 502 if 5xx]
  -> compound = compose_assembly(intent)                  [500 geometry_rebuild_failed]
  -> views = project_views(compound)                      [500 view_projection_failed]
  -> report_bytes = build_report_pdf(...)                 [500 report_build_failed]
  -> drawing_bytes = build_drawing_pdf(views, mass, intent, material, now_utc)
                                                          [500 drawing_build_failed]
  -> asyncio.gather(
       storage.upload(cache_key, "report",  report_bytes),
       storage.upload(cache_key, "drawing", drawing_bytes),
     )                                                    [502 gcs_upload_failed retry-once]
  -> Deliverables{
       report_pdf_url, drawing_pdf_url,
       step_url=geometry_artifacts.step_url,
       glb_url=geometry_artifacts.glb_url,
       svg_url=geometry_artifacts.svg_url,
       cache_hit=False, cache_key,
     }
  -> cache.put(key, Deliverables)
  -> 200 JSON
```

### 5.2 Happy path — cache hit (~50 ms)

```
POST /document {...same...}
  -> validate, hash
  -> cache.get(key) returns Deliverables
  -> return Deliverables with cache_hit=True (same URLs)
```

### 5.3 HTTP Contract

```
POST /document
  Request:   { intent, analysis_result, natural_report, geometry_artifacts, session_id? }
  Response:  200 Deliverables
             422 { code, message, field?, details? }
             500 { code, message, stage?, details? }
             502 { code: "gcs_upload_failed", message, retry_after }
```

`Deliverables` JSON shape:

```json
{
  "report_pdf_url":  "https://storage.googleapis.com/.../documents/abc.../report.pdf?...",
  "drawing_pdf_url": "https://storage.googleapis.com/.../documents/abc.../drawing.pdf?...",
  "step_url":  "<echoed>",
  "glb_url":   "<echoed>",
  "svg_url":   "<echoed>",
  "cache_hit": false,
  "cache_key": "abcdef0123456789"
}
```

---

## 6. Error Handling and Observability

### 6.1 Retry policy

| Error | Server retries | Client action |
|---|---|---|
| `invalid_input` | 0 | Fix payload, resend |
| `geometry_rebuild_failed` | 0 | Adjust intent fields |
| `view_projection_failed` | 0 | Surface to user; rare |
| `report_build_failed` | 0 | Bug — log + report |
| `drawing_build_failed` | 0 | Bug — log + report |
| `gcs_upload_failed` | **1 with 1 s backoff** | Wait `retry_after` (5 s) then re-POST |
| `internal_error` | 0 | Surface to user |

### 6.2 Degraded mode

Out of scope for MVP. Optional stretch: pre-baked `data/document_artifacts/{cache_key}/{report,drawing}.pdf` on disk for the three hero hashes, served if GCS is unreachable.

### 6.3 Observability

Reuses S1's structlog logger.

```
logger.info("document_request_started",
    intent_type=intent.type, verdict=analysis.verdict.value,
    cache_key=key, session_id=session_id)

logger.info("document_cache_hit", cache_key=key, latency_ms=elapsed)

logger.info("document_completed",
    cache_key=key, latency_ms=elapsed,
    report_size_kb=report_bytes_len/1024,
    drawing_size_kb=drawing_bytes_len/1024,
    views=["front","side","iso"], svg_embedded=true|false)

logger.warning("document_failed",
    code=err.code.value, intent_type=intent.type, stage=err.stage)
```

**Metrics**:
```
document.request_count{intent_type, verdict, cache_hit}
document.latency_ms{intent_type, stage}      # fetch_svg / compose / project / build_report / build_drawing / upload
document.failure_count{code, stage}
document.pdf_size_bytes{pdf_type}            # histogram
```

### 6.4 PII / Security

- Inputs carry no PII
- PDFs cached in GCS for 24 h via signed URL TTL — no auto-delete, lifecycle policy deferred
- Rate limit **10 req/min per IP** (heaviest endpoint)
- GCS bucket CORS: same as S2 (`*.vercel.app` + `localhost:3000`)

---

## 7. Testing Strategy

### 7.1 Why PDF testing is different

PDFs are binary blobs. Tests verify **invariants** (magic bytes, page count, contains expected labels via text extraction) — not byte equality. Real GCS is never used in CI; a `FakeGcsClient` is the only acceptable test double.

### 7.2 Test pyramid

| Layer | Type | What it verifies | Count |
|---|---|---|---|
| Unit — domain | pytest | Deliverables / DocumentRequest roundtrip + DocumentErrorCode stable | 4 |
| Unit — theme | pytest | Constants exist + verdict color map covers PASS/WARN/FAIL | 2 |
| Unit — cache | pytest | key stability, hit/miss, changes on intent/analysis/narrative change, math.inf safe | 6 |
| Unit — views | pytest + real build123d | 3 SVG bytes, each begins `<?xml`/`<svg`, all three differ | 4 |
| Unit — report | pytest + reportlab + pypdf | `%PDF-` magic, 5 pages, contains intent.type / verdict / SF / formula | 8 |
| Unit — drawing | pytest + reportlab + pypdf | `%PDF-` magic, 1 page, contains bbox dims + material name | 5 |
| Unit — storage (FakeGcs) | pytest | upload returns signed URL, retry-once-on-fail, hard fail after second | 4 |
| Unit — pipeline | pytest (FakeGcs + FakeSvgFetcher) | cache miss happy, cache hit shortcut, error propagation | 6 |
| Component — router | pytest + TestClient + fakes | 200 + 422 paths + cache_hit response | 6 |
| Integration — heroes | pytest -m integration (FakeGcs) | 3 hero bundles produce valid PDFs | 3 |

**Total ~48 tests. Suite target < 8 s** (PDF builds + build123d projections dominate runtime).

### 7.3 Test doubles

`apps/backend/tests/fakes/fake_gcs_client.py`:

```python
class FakeGcsClient:
    """In-memory stand-in for google.cloud.storage.Client.

    Stores uploaded bytes per (bucket, name). Returns signed URLs of the form
    'fake://{bucket}/{name}?ttl=24h'. Tests assert on stored bytes + URL shape.
    """
```

`apps/backend/tests/fakes/fake_svg_fetcher.py`:

```python
class FakeSvgFetcher:
    """Returns canned SVG bytes for any URL. Tests inject a small valid SVG."""
```

### 7.4 Critical test cases

```python
def test_report_pdf_has_five_pages():
    pdf = build_report_pdf(...)
    assert pdf.startswith(b"%PDF-")
    assert _pypdf_page_count(pdf) == 5

def test_report_pdf_contains_verdict():
    pdf = build_report_pdf(intent, analysis_warn, narrative, geometry, material, svg, ...)
    text = _pypdf_extract_text(pdf)
    assert "WARN" in text.upper()
    assert "Safety factor" in text
    assert analysis_warn.formula in text

def test_report_pdf_includes_facts_used_footer():
    narrative = NaturalReport(summary="x", facts_used=["stress_max_mpa", "safety_factor"])
    pdf = build_report_pdf(...)
    text = _pypdf_extract_text(pdf)
    assert "stress_max_mpa" in text
    assert "safety_factor" in text

def test_drawing_pdf_has_one_page_with_bbox_labels():
    pdf = build_drawing_pdf(views, mass, intent, material, now_utc_iso="2026-05-16T12:00:00Z")
    assert _pypdf_page_count(pdf) == 1
    text = _pypdf_extract_text(pdf)
    assert "Width" in text
    assert "Height" in text
    assert "Depth" in text

def test_views_returns_three_distinct_svgs():
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert set(views.keys()) == {"front", "side", "iso"}
    assert all(v.lstrip().startswith(b"<?xml") or v.lstrip().startswith(b"<svg")
               for v in views.values())
    assert views["front"] != views["side"]

def test_cache_key_changes_when_narrative_summary_changes():
    k1 = DocumenterCache.key_for(intent, analysis,
                                  NaturalReport(summary="A"))
    k2 = DocumenterCache.key_for(intent, analysis,
                                  NaturalReport(summary="B"))
    assert k1 != k2

def test_pipeline_cache_hit_skips_pdf_build(fake_gcs, fake_fetcher):
    """Second call with identical inputs returns cached Deliverables, no build, no upload."""
    ...

def test_storage_retries_once_on_transient_failure(failing_once_fake_gcs):
    url = await storage.upload(...)
    assert failing_once_fake_gcs.upload_count == 2
    assert url.startswith("fake://")
```

### 7.5 Integration

Three hero (intent, analysis, narrative) bundles run end-to-end with FakeGcs. They reuse the `HERO_INTENTS` from `scripts/generate_demo_artifacts.py`, extended with operational fields (same `extend_with_operational` helper used by S3 and S4 integration tests), plus canned `AnalysisResult` and `NaturalReport` payloads matching what S3+S4 actually produce.

```python
@pytest.mark.integration
def test_hero_flywheel_document_bundles_all_artifacts(
    document_client, hero_flywheel_request
):
    r = document_client.post("/document", json=hero_flywheel_request)
    assert r.status_code == 200
    d = r.json()
    assert d["report_pdf_url"].startswith("fake://")
    assert d["drawing_pdf_url"].startswith("fake://")
    assert d["step_url"] == hero_flywheel_request["geometry_artifacts"]["step_url"]
```

### 7.6 Coverage gate

`--cov-fail-under=85` on `services/documenter/`. Matches the S2/S3/S4 standard.

---

## 8. Acceptance Criteria

**Functional**:
- [ ] `services/documenter/` exists with `domain/`, `pdf/`, `views.py`, `storage.py`, `cache.py`, `svg_fetcher.py`, `pipeline.py`, `api/`
- [ ] `POST /document` sync JSON returns `Deliverables` with 5 URLs (2 generated + 3 echoed) + `cache_hit` + `cache_key`
- [ ] `report_pdf` has 5 pages (cover, intent, geometry, analysis+narrative, appendix)
- [ ] `drawing_pdf` has 1 page with 3 views + bbox labels + title block
- [ ] PDFs stored under `gs://{bucket}/documents/{cache_key}/{name}.pdf` with 24-hour signed URLs
- [ ] Cache hit transparent (no rebuild, no upload, same response shape)
- [ ] Service mounted in `apps/backend/main.py`
- [ ] 3 hero bundles pass integration tests against FakeGcs
- [ ] `reportlab>=4.2` added to `pyproject.toml` deps
- [ ] `pypdf>=4.0` added to `pyproject.toml` dev deps

**Non-functional**:
- [ ] Cache hit p95 < 100 ms
- [ ] Cache miss p95 < 2 s (fetch SVG + compose + project + 2x PDF + 2x upload)
- [ ] PDF build sub-suite < 3 s
- [ ] Full test suite (excluding `-m integration`) < 8 s
- [ ] PDFs open in macOS Preview + Chrome (manual smoke pre-demo)

**Quality**:
- [ ] Coverage ≥ 85 % in `services/documenter/`
- [ ] ruff + mypy clean
- [ ] Zero `print()` — structlog only
- [ ] `pdf/report.py` < 250 LOC
- [ ] `pdf/drawing.py` < 150 LOC
- [ ] `pdf/theme.py` < 80 LOC
- [ ] `views.py` < 80 LOC
- [ ] `pipeline.py` < 150 LOC
- [ ] Each page builder in `pdf/report.py` is a pure helper `(canvas, data) -> None`

**Documentation**:
- [ ] `services/documenter/README.md` with curl example + runbook
- [ ] This spec doc committed
- [ ] Plan doc at `docs/superpowers/plans/2026-05-16-s5-documenter.md`

---

## 9. Demo Script

```
0:00-0:05  User has finished S1+S2+S3+S4. UI shows the viewer, the mass panel,
           the safety factor badge, and the narrative.
           User clicks "Download report".
           Frontend POSTs /document with the full bundle.

0:05-0:07  ~600 ms server-side. UI shows a brief "Generating documents..."

0:07-0:10  Deliverables JSON arrives. UI shows two new buttons:
              [Download report PDF]   [Download drawing PDF]
           Plus persistent buttons:
              [STEP file] [GLB file (3D viewer)] [SVG section]

0:10-0:20  User clicks "Download report PDF".
           macOS Preview opens, video shows:
             Page 1: Cover with WARN badge
             Page 2: Intent + material table
             Page 3: Geometry stats + section view
             Page 4: Stress 193.7 MPa, SF 1.29 WARN; narrative below
             Page 5: Material props + assumptions

0:20-0:25  User clicks "Download drawing PDF".
           Single page with front/side/iso views, bbox labels, title block.

0:25-0:30  Voice-over: "The same pipeline that wrote the prose drew the part
                        and signed the URL — no human in the loop."
```

If the design cannot support this flow, the design is wrong.

---

## 10. Open Questions

None at approval time. All decisions (deliverables, API shape, language, storage, caching, retry policy, module layout, PDF library, SVG embedding, view projections, rate limit, pre-baked fallback) are confirmed in this session.

---

## 11. Next Step

Invoke `superpowers:writing-plans` to decompose this spec into an implementation plan.
