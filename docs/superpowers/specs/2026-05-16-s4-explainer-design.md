# S4 Explainer — Design Spec

**Date**: 2026-05-16
**Subsystem**: S4 — Explainer Service
**Parent document**: [DESIGN.md](../../../DESIGN.md)
**Depends on**: [S1 Interpreter spec](2026-04-18-s1-interpreter-design.md), [S3 Physics spec](2026-05-16-s3-physics-design.md)
**Status**: Approved, ready for implementation plan

---

## 1. Context and Purpose

S4 Explainer turns the numerical output of S3 (`AnalysisResult`) into accessible natural language. It receives the `DesignIntent` (what the user asked for) and the `AnalysisResult` (what S3 computed), and returns a structured `NaturalReport` with four sections: a plain-English summary, risk bullets, suggestion bullets, and analogy bullets.

**Why this subsystem matters**: S3 produces numbers; S4 makes those numbers *understandable*. The hackathon rubric weighs storytelling at 30 points — S4 is what materializes the engineering on screen for the demo video and what an end-user actually reads. It is also the unblock for S5 (Documenter): the PDF report renders `NaturalReport` as its prose.

**Why the scope is restricted to a single LLM call (no multi-turn refinement, no bilingual)**: deadline 2026-05-18 (~45 h after this spec). The English-only path with a single Gemma 4 streaming call is what the demo video records; bilingual ES + EN and "ask the report follow-up questions" are post-hackathon work.

**Anti-fabrication rule** (verbatim from DESIGN.md §2 S4): *"NARRATES only real numerical data; fabricating values is forbidden."* This spec turns that rule into a mechanical contract: the LLM is given a FACTS table with every legal value it may cite, instructed in the system prompt to refuse to invent, and required to echo back the cited labels in `facts_used` for self-audit.

---

## 2. Scope and Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Output shape | **JSON structured (`{summary, risks, suggestions, analogies, facts_used}`)** | Pydantic-validated; easy for S5 PDF to format; testable; survives prompt drift |
| API shape | **`POST /explain` SSE streaming** | Mirrors S1 SSE infra; lets the demo show text appearing token-by-token; structured `final` event at the end |
| Languages | **English only for MVP** | Bilingual post-hackathon; rule from CLAUDE.md is acknowledged and deferred |
| Caching | **In-memory dict keyed by `sha256(intent_values + analysis_values)`** | Trivial; same Gemma input → same key → idempotent demo; reset on process restart is acceptable |
| Retries | **0 on Vertex errors (client retries), 1 on JSON parse failure** | Vertex failures need backoff; LLM JSON malformation can usually be fixed with a stricter prompt |
| Module layout | **`apps/backend/services/explainer/` sibling of `services/{interpreter,geometry,physics}/`** | Each subsystem replaceable per CLAUDE.md principle |
| LLM client | **Reuse `VertexGemmaClient`** with a new method `generate_text_streaming(system, user)` | One small addition (~30 LOC) to S1's client; second instance with `temperature=0.3` for S4 |
| Grounding strategy | **Facts table in user prompt + `facts_used` self-audit field in output** | Mechanical contract that scales beyond prompt-engineering tricks |
| Demo fallback | **Out of scope for MVP — add pre-baked hero JSONs only if time permits** | Cache + retry already cover the demo path; Vertex outage during a 30-second demo is a low-probability tail risk |
| Rate limit | **20 req/min per IP** | Heavier than S2's 10 (Gemma costs money) but lower than S1's 30 |

---

## 3. Architecture

Four logical layers + a transversal cache.

```
HTTP Layer        POST /explain (FastAPI SSE)
                  ├─ DTO validate (Pydantic)
                  └─ extract intent + analysis_result from request

Prompt Layer      Facts table + system prompt
                  ├─ facts.py: AnalysisResult + DesignIntent -> dict[str, str]
                  └─ prompt.py: load system prompt + render user prompt

Generation Layer  Streaming Gemma call + JSON parse
                  ├─ generator.py: orchestrate cache lookup -> Vertex stream -> parse -> retry -> cache.put
                  └─ uses VertexGemmaClient (instance #2, temp=0.3)

Cache Layer       In-memory dict
                  └─ cache.py: sha256(values) -> NaturalReport
```

### Layer responsibilities

**HTTP Layer** — FastAPI router that accepts `POST /explain {intent: DesignIntent, analysis_result: AnalysisResult, session_id?: str}` and emits a Server-Sent Events stream. The stream always ends with exactly one `final` or `error` event.

**Prompt Layer** — `facts.py:build_facts(intent, result)` returns a flat `dict[str, str]` containing every numerical value Gemma is *allowed* to cite. `prompt.py` loads the system prompt from `prompts/explainer_system.md` (mirror of S1's `prompts/interpreter_system.md` pattern) and renders the user prompt by embedding the facts table.

**Generation Layer** — `generator.py:Explainer.explain_streaming(intent, result)` is an async generator that:
1. Computes the cache key. On hit, emits `final` and returns.
2. Builds prompts.
3. Calls `VertexGemmaClient.generate_text_streaming(system, user)` and relays each chunk as an SSE `chunk` event.
4. Parses the accumulated text as `NaturalReport` JSON. If parsing fails, retries once with a stricter prompt suffix.
5. Stores result in cache, emits `final`.

**Cache Layer** — `cache.py:ExplainerCache` is a thin wrapper around a `dict`. The key is `sha256` of a canonical JSON containing the intent values, key analysis_result numbers, material name, and verdict. Process-local; reset on restart.

### Key design principle

**Honesty in numerics is enforced by contract, not by hope.** The FACTS table is the LLM's only legal vocabulary for numbers. The `facts_used` output field is the LLM's self-attestation of which labels it cited. Tests can verify that every number in `summary/risks/suggestions/analogies` is also in `facts_used`, and that every label in `facts_used` exists in the FACTS table. The rule from DESIGN.md becomes auditable.

---

## 4. Components

### 4.1 Domain Models

`services/explainer/domain/models.py`:

```python
from pydantic import BaseModel, Field

from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class NaturalReport(BaseModel):
    summary: str = Field(..., description="<=80 word plain-English summary")
    risks: list[str] = Field(default_factory=list, description="1-4 short bullets")
    suggestions: list[str] = Field(default_factory=list, description="1-4 actionable bullets")
    analogies: list[str] = Field(default_factory=list, description="1-2 lay analogies")
    facts_used: list[str] = Field(default_factory=list, description="exact FACTS labels cited")


class ExplainRequest(BaseModel):
    intent: DesignIntent
    analysis_result: AnalysisResult
    session_id: str | None = None
```

### 4.2 Error Taxonomy

`services/explainer/domain/errors.py`:

```python
class ExplainErrorCode(StrEnum):
    INVALID_INPUT          = "invalid_input"           # 422
    GEMMA_TIMEOUT          = "gemma_timeout"           # 504
    GEMMA_RATE_LIMITED     = "gemma_rate_limited"      # 429
    GEMMA_FAILED           = "gemma_failed"            # 502
    REPORT_PARSE_FAILED    = "report_parse_failed"     # 502
    REPORT_SCHEMA_INVALID  = "report_schema_invalid"   # 502
    INTERNAL_ERROR         = "internal_error"          # 500

class ExplainError(BaseModel):
    code: ExplainErrorCode
    message: str
    retry_after: int | None = None
    details: dict[str, Any] | None = None

    @property
    def http_status(self) -> int:
        return {
            ExplainErrorCode.INVALID_INPUT: 422,
            ExplainErrorCode.GEMMA_TIMEOUT: 504,
            ExplainErrorCode.GEMMA_RATE_LIMITED: 429,
        }.get(self.code, 500)

    def raise_as(self) -> None:
        raise ExplainException(self)


class ExplainException(RuntimeError):  # noqa: N818 -- intentional distinction
    def __init__(self, error: ExplainError) -> None:
        super().__init__(error.message)
        self.error = error
```

### 4.3 Facts table

`services/explainer/facts.py`:

```python
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

Floats formatted to 2-3 significant digits to keep the prompt compact. The `notes` field on `AnalysisResult` is NOT in the facts table — Gemma can read prose context separately if needed (deferred).

### 4.4 Prompt template

`apps/backend/prompts/explainer_system.md`:

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
     "risks":      ["<short bullet>", ...],          // 1-4 items
     "suggestions":["<short bullet>", ...],          // 1-4 items
     "analogies":  ["<short bullet>", ...],          // 1-2 items
     "facts_used": ["<label>", ...]                  // labels you cited
   }
4. Every number you cite in summary/risks/suggestions/analogies MUST have
   its label in facts_used.
5. Match the verdict tone:
   - PASS: confident, positive, brief
   - WARN: cautious, "near limit", suggest verification
   - FAIL: serious; explain why; suggest one concrete fix
6. Keep the language plain. Avoid jargon unless you also define it.
```

`services/explainer/prompt.py`:

```python
def load_system_prompt(prompts_dir: Path) -> str:
    return (prompts_dir / "explainer_system.md").read_text(encoding="utf-8")


def build_user_prompt(facts: dict[str, str]) -> str:
    facts_block = "\n".join(f"  {k} = {v}" for k, v in facts.items())
    return f"FACTS:\n{facts_block}\n\nProduce the JSON report now."


def build_strict_retry_prompt(facts: dict[str, str]) -> str:
    base = build_user_prompt(facts)
    return base + "\n\nIMPORTANT: Output ONLY valid JSON. No prose, no code fences."
```

### 4.5 Generator

`services/explainer/generator.py`:

```python
class Explainer:
    def __init__(
        self,
        *,
        gemma: VertexGemmaClient,
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
            yield ExplainEvent(event="final", data={
                "report": cached.model_dump(),
                "cache_hit": True,
                "cache_key": key,
            })
            return

        facts = build_facts(intent, result)
        yield ExplainEvent(event="progress", data={"step": "generating"})

        try:
            accumulated = ""
            async for chunk in self._gemma.generate_text_streaming(
                system_prompt=self._system,
                user_prompt=build_user_prompt(facts),
            ):
                accumulated += chunk
                yield ExplainEvent(event="chunk", data={"text": chunk})
        except VertexTimeout:
            ExplainError(code=ExplainErrorCode.GEMMA_TIMEOUT, ...).raise_as()
            raise AssertionError("unreachable") from None
        except VertexRateLimited:
            ExplainError(code=ExplainErrorCode.GEMMA_RATE_LIMITED, ...).raise_as()
            raise AssertionError("unreachable") from None
        except Exception as exc:  # bridge unknown Vertex failures
            ExplainError(code=ExplainErrorCode.GEMMA_FAILED, ...).raise_as()
            raise AssertionError("unreachable") from exc

        yield ExplainEvent(event="progress", data={"step": "parsing"})
        report = self._parse_or_retry(accumulated, facts)

        self._cache.put(key, report)
        yield ExplainEvent(event="final", data={
            "report": report.model_dump(),
            "cache_hit": False,
            "cache_key": key,
        })

    async def _parse_or_retry(
        self, first_text: str, facts: dict[str, str]
    ) -> NaturalReport:
        try:
            return NaturalReport.model_validate_json(_strip_codefence(first_text))
        except (ValidationError, json.JSONDecodeError):
            pass
        retry_text = ""
        async for chunk in self._gemma.generate_text_streaming(
            system_prompt=self._system,
            user_prompt=build_strict_retry_prompt(facts),
        ):
            retry_text += chunk
        try:
            return NaturalReport.model_validate_json(_strip_codefence(retry_text))
        except (ValidationError, json.JSONDecodeError) as exc:
            ExplainError(
                code=ExplainErrorCode.REPORT_PARSE_FAILED,
                message=f"Gemma returned malformed JSON twice; last error: {exc}",
                details={"last_text": retry_text[:500]},
            ).raise_as()
            raise AssertionError("unreachable") from exc


def _strip_codefence(text: str) -> str:
    """Strip ```json ... ``` if the model wrapped JSON in a code fence."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    if s.startswith("json\n"):
        s = s[5:]
    return s.strip()
```

`_parse_or_retry` is intentionally NOT a generator — it does not stream the retry chunks (the user has already seen one stream). The retry call's chunks are absorbed silently.

### 4.6 Cache

`services/explainer/cache.py`:

```python
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
                k: f.value for k, f in sorted(intent.fields.items())
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

`math.inf` safety factors (zero-load cases) are rounded — Python's `json.dumps` rejects them by default. Solution: store `safety_factor` as a string when not finite, or skip it from the hash entirely (every other field already disambiguates).

### 4.7 API Router

`services/explainer/api/router.py`:

```python
router = APIRouter(tags=["explainer"])

@router.post("/explain")
async def explain(req: ExplainRequest, app_req: Request) -> StreamingResponse:
    explainer: Explainer = app_req.app.state.explainer
    sse = explainer.explain_streaming(req.intent, req.analysis_result)
    return StreamingResponse(_to_sse(sse), media_type="text/event-stream")
```

SSE serialization helper copies the same pattern as `services/geometry/api/streaming.py:serialize_geometry_sse`. The exception handler maps `ExplainException` to either a streaming `error` event (if the stream had already started) or a JSON error response (if it failed pre-stream).

### 4.8 VertexGemmaClient extension

One new method added to `services/interpreter/agent/vertex_gemma.py`:

```python
async def generate_text_streaming(
    self,
    *,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    """Plain text streaming, no tools. Yields raw text chunks.

    Uses response_mime_type='application/json' for built-in JSON mode.
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

    async for ev in stream:
        text = getattr(ev, "text", "") or ""
        if text:
            yield text
```

Two thin sentinel exceptions (`VertexTimeout`, `VertexRateLimited`) are defined in `services/interpreter/agent/gemma_client.py` so the explainer can catch them without importing FastAPI's `HTTPException`. Both inherit from `RuntimeError`; carrying a message only — no payload.

S4 instantiates a SECOND `VertexGemmaClient` with `temperature=0.3` (S1 uses 0.2), wired in `main.py`.

---

## 5. Data Flow

### 5.1 Happy path — cache miss (~3-8 s)

```
POST /explain {intent, analysis_result}
  -> Pydantic validate                          [422 invalid_input]
  -> compute cache_key
  -> cache.get(key) is None
  -> emit progress {step: "generating"}
  -> build facts table + user prompt
  -> Vertex Gemma streaming (temp 0.3, JSON mime, max 2048 tokens, 10s timeout)
  -> for each text chunk: emit chunk {text: "..."}
  -> emit progress {step: "parsing"}
  -> strip ```json``` if present
  -> parse JSON -> NaturalReport validate
  -> cache.put(key, report)
  -> emit final {report, cache_hit: false, cache_key}
```

### 5.2 Happy path — cache hit (~50 ms)

```
POST /explain {...same...}
  -> validate, hash
  -> cache.get(key) returns NaturalReport
  -> emit final {report, cache_hit: true, cache_key}
```

No `progress`, no `chunk` events on cache hit. Client-side a cache-hit response renders the full report instantly.

### 5.3 Retry path — first JSON malformed

```
... (stream chunks of malformed text) ...
  -> parse fails (ValidationError or JSONDecodeError)
  -> Vertex called again with stricter prompt suffix
  -> retry chunks accumulated SILENTLY (not streamed to client)
  -> parse second response
  -> success: cache + final
  -> failure: emit error {code: report_parse_failed}
```

The retry is silent to the client so it doesn't see "double output". A `progress {step: "retrying"}` event is *not* emitted to keep the SSE contract simple.

### 5.4 HTTP / SSE Contract

```
POST /explain
  Request:   { intent: DesignIntent, analysis_result: AnalysisResult, session_id?: string }
  Response:  200 text/event-stream
             422 { code: "invalid_input", message, details? }
             503 { code: "service_unavailable", retry_after? }   -- only if Vertex unreachable pre-stream
```

```typescript
event: progress
data: { step: "generating" | "parsing", message?: string }

event: chunk
data: { text: string }            // raw Gemma token output, may be partial JSON

event: final
data: {
  report: NaturalReport,
  cache_hit: boolean,
  cache_key: string
}

event: error
data: {
  code: ExplainErrorCode,
  message: string,
  retry_after?: number,
  details?: object
}
```

Stream always ends with exactly one `final` or `error` event.

---

## 6. Error Handling and Observability

### 6.1 Retry policy

| Error | Server retries | Client action |
|---|---|---|
| `invalid_input` | 0 | Fix request, resend |
| `gemma_timeout` | 0 | Wait `retry_after` (5 s), resend |
| `gemma_rate_limited` | 0 | Wait `retry_after` (30 s), resend |
| `gemma_failed` | 0 | Wait `retry_after` (10 s), resend |
| `report_parse_failed` | **1 (built into generator)** | If still fails, surface to user |
| `report_schema_invalid` | 0 (counted as parse failure) | Same as above |

### 6.2 Degraded mode

Out of scope for MVP. If Vertex is unreachable, the request fails with `gemma_failed` and the client surfaces the error. Pre-baked hero report JSONs under `apps/backend/data/explain_artifacts/{cache_key}.json` are an OPTIONAL stretch goal added only if implementation time remains.

### 6.3 Observability

Reuses S1's structlog logger.

```python
logger.info("explain_request_started",
    intent_type=intent.type, verdict=result.verdict.value, cache_key=key,
    session_id=session_id)

logger.info("explain_cache_hit",
    cache_key=key, latency_ms=elapsed)

logger.info("explain_completed",
    cache_key=key, parse_retries=0 or 1, latency_ms=elapsed,
    summary_chars=len(report.summary),
    risks_count=len(report.risks),
    facts_cited=len(report.facts_used))

logger.warning("explain_failed",
    code=err.code.value, intent_type=intent.type, cache_key=key)
```

**Metrics**:
```
explain.request_count{intent_type, verdict, cache_hit}
explain.latency_ms{intent_type, stage}        # generating / parsing
explain.parse_retry_count
explain.failure_count{code}
```

### 6.4 PII and Security

- Intents and AnalysisResults contain no PII (mechanical specs only)
- Reports are cached in-memory only; process restart wipes them
- `session_id` is the only identifier that flows through; it is opaque
- Rate limit **20 req/min per IP** (heavier than S2's 10 because each call costs Vertex tokens)

---

## 7. Testing Strategy

### 7.1 Why LLM testing is different

The exact text Gemma returns is non-deterministic even at `temperature=0.3`. Tests must verify **invariants** (schema validity, facts grounding, retry behavior, SSE event order) rather than exact strings. Real Vertex calls are reserved for the manual pre-demo smoke; CI uses a `FakeGemmaTextClient`.

### 7.2 Test pyramid

| Layer | Type | What it verifies | Count |
|---|---|---|---|
| Unit — models | pytest | NaturalReport / ExplainErrorCode stability | 4 |
| Unit — facts | pytest | build_facts shape for each hero | 5 |
| Unit — prompt | pytest | system prompt loads + carries anti-fab rule; user prompt embeds facts | 3 |
| Unit — cache | pytest | key stability + hit/miss + value-change invalidation | 5 |
| Unit — generator | pytest + FakeGemma | streaming chunks, JSON parse, retry-once, error mapping | 8 |
| Component — router | pytest + TestClient (FakeGemma) | SSE event order, cache-hit shortcut, 422 paths | 7 |
| Integration — heroes | pytest -m integration (FakeGemma) | end-to-end SSE for 3 hero (intent, AnalysisResult) pairs | 3 |

**Total ~35 tests. Suite target < 5 s.**

### 7.3 FakeGemmaTextClient

`apps/backend/tests/fakes/fake_gemma_text.py`:

```python
class FakeGemmaTextClient:
    """Deterministic stand-in for VertexGemmaClient streaming text gen."""

    def __init__(
        self,
        chunks_per_call: list[list[str]],
        raise_on_first: Exception | None = None,
    ) -> None:
        self._chunks_per_call = chunks_per_call
        self._call_count = 0
        self._raise_first = raise_on_first

    async def generate_text_streaming(self, *, system_prompt, user_prompt):
        self._call_count += 1
        if self._call_count == 1 and self._raise_first:
            raise self._raise_first
        idx = min(self._call_count - 1, len(self._chunks_per_call) - 1)
        for chunk in self._chunks_per_call[idx]:
            yield chunk
```

Test scenarios injected:
- Valid JSON in one chunk
- Valid JSON split across many chunks (verifies accumulation)
- Malformed JSON on call 1, valid JSON on call 2 (verifies retry)
- Malformed JSON on calls 1 + 2 (verifies hard error)
- `VertexTimeout` on call 1 (verifies error mapping)

### 7.4 Critical anti-fabrication tests

```python
def test_facts_table_for_flywheel_contains_all_solver_outputs():
    intent = _flywheel_intent()
    result = _flywheel_result(sf=1.29, verdict=Verdict.WARN)
    facts = build_facts(intent, result)
    assert "stress_max_mpa" in facts
    assert "safety_factor" in facts
    assert "material_yield_mpa" in facts
    assert "verdict" in facts
    assert facts["verdict"] == "WARN"

def test_system_prompt_carries_anti_fabrication_rule():
    p = load_system_prompt(_PROMPTS_DIR)
    assert "NEVER invent" in p or "NEVER fabric" in p.replace("\n", " ")
    assert "FACTS table" in p
    assert "facts_used" in p

def test_user_prompt_embeds_every_facts_label():
    facts = {"stress_max_mpa": "193.7 MPa", "safety_factor": "1.29"}
    rendered = build_user_prompt(facts)
    assert "stress_max_mpa = 193.7 MPa" in rendered
    assert "safety_factor = 1.29" in rendered
```

### 7.5 Integration tests

```python
@pytest.mark.integration
def test_hero_flywheel_explain_emits_final_warn_narrative(
    explain_client, hero_intent_flywheel, hero_analysis_flywheel
):
    body = {
        "intent": hero_intent_flywheel.model_dump(),
        "analysis_result": hero_analysis_flywheel.model_dump(),
    }
    sse = explain_client.post("/explain", json=body)
    events = _parse_sse(sse.text)
    final = events[-1]
    assert final["event"] == "final"
    report = final["data"]["report"]
    assert report["summary"]
    assert report["facts_used"]                            # non-empty
    assert "WARN" in report["summary"] or any("WARN" in r for r in report["risks"])
```

Three heroes (flywheel, hydro, shelter) each get one integration test with a canonical `AnalysisResult` synthesized via S3 solvers and a FakeGemma returning a scripted valid JSON tuned to the verdict.

### 7.6 Coverage gate

`--cov-fail-under=85` on `services/explainer/`. Matches S2/S3 standard.

---

## 8. Acceptance Criteria

**Functional**:
- [ ] `services/explainer/` exists with `domain/`, `facts.py`, `prompt.py`, `generator.py`, `cache.py`, `api/`
- [ ] `POST /explain` SSE emits `progress`, `chunk`, `final`, `error` events in spec order
- [ ] `NaturalReport {summary, risks, suggestions, analogies, facts_used}` validated via Pydantic
- [ ] Cache hit transparent (no chunks emitted, same `final` shape)
- [ ] One JSON-parse retry built into generator
- [ ] `VertexGemmaClient.generate_text_streaming` added; S1 untouched in semantics
- [ ] S4 instantiates a second `VertexGemmaClient` with `temperature=0.3`
- [ ] Service mounted in `apps/backend/main.py`
- [ ] 3 hero (intent + AnalysisResult) pairs pass integration tests against FakeGemma

**Non-functional**:
- [ ] Cache hit p95 < 100 ms
- [ ] Cache miss p95 < 8 s (Vertex streaming, network-dependent)
- [ ] Test suite (excluding `-m integration` mark) < 5 s
- [ ] Rate limit 20 req/min per IP (infra-level, documented)
- [ ] Zero PII in cache or logs

**Quality**:
- [ ] Coverage ≥ 85 % in `services/explainer/`
- [ ] ruff + mypy clean
- [ ] Zero `print()` — structlog only
- [ ] `facts.py` < 80 LOC
- [ ] `prompt.py` < 60 LOC
- [ ] `generator.py` < 120 LOC
- [ ] `cache.py` < 70 LOC

**Documentation**:
- [ ] `services/explainer/README.md` with curl example + runbook
- [ ] This spec doc committed
- [ ] System prompt lives in `apps/backend/prompts/explainer_system.md`

---

## 9. Demo Script

```
0:00-0:05  User just got AnalysisResult from S3 (flywheel WARN, SF=1.29).
           Frontend POSTs /explain with intent + analysis_result.

0:05-0:10  SSE progress event: "generating".
           Chunk events start arriving — text appears live:
             "The flywheel design hits the energy target..."
             "...with a safety factor of 1.29, the design is in the WARN band..."

0:10-0:15  Continued streaming:
             "...rotor stress reaches 193.7 MPa against a 250 MPa yield limit..."
             SSE progress: "parsing".

0:15-0:18  SSE final event arrives with parsed NaturalReport.
           UI now shows the four sections:
             Summary: <prose>
             Risks: 3 bullets
             Suggestions: 2 bullets
             Analogies: 1 bullet
             (small text) "Facts cited: stress_max_mpa, safety_factor, ..."

0:18-0:25  Voice-over: "Notice that every number on screen came from S3 —
                       the LLM is not allowed to invent."
```

If the design cannot support this flow, the design is wrong.

---

## 10. Open Questions

None at approval time. All decisions (output shape, API shape, language, cache, retry, layout, grounding strategy, rate limit) are confirmed in this session.

---

## 11. Next Step

Invoke `superpowers:writing-plans` to decompose this spec into an implementation plan.
