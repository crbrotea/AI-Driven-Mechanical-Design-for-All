# Frontend Wiring (S1→S5 end-to-end) — Design Spec

**Date**: 2026-05-16
**Subsystem**: Frontend `/design` page + Cloud Run deploy
**Parent document**: [DESIGN.md](../../../DESIGN.md)
**Depends on**: S1-S5 specs and live backend (this session committed: 67f2863, 844c46f). Existing frontend infra spec `2026-04-19-frontend-design.md`.
**Status**: Approved, ready for implementation plan

---

## 1. Context and Purpose

The backend pipeline S1→S2→S3→S4→S5 is live and verified via curl. The frontend already has `/design` page with 3-column layout (FormPanel / ViewerPanel / ChatPanel), plus hooks for `useInterpretStream` (S1) and `useGenerateStream` (S2). What is missing is the UI that consumes S3 / S4 / S5 — without it, the demo video only shows form → 3D viewer, losing the engineering narrative (S4) and the deliverables (S5) that anchor the rubric's Storytelling and Technical Depth tracks.

**Why this matters**: the hackathon is judged on 40 Impact + 30 Storytelling + 30 Technical Depth. The 5-page engineering report PDF and the streaming AI narrative are the most visible "this is real engineering, not a toy" signals. Without them the demo is a 3D viewer with a mass number.

**Why now**: ~46 h to deadline 2026-05-18. Backend is the bottleneck removed; frontend wiring is the last code work before the video record.

**Scope of this spec**: extend `/design` with per-stage manual triggers ("Analyze", "Explain", "Generate documents"), three new hooks, three new component dirs, and a Cloud Run deploy of the backend so the frontend (Vercel-hosted) can talk to it from production.

---

## 2. Scope and Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Pipeline trigger | **Per-stage manual buttons** | Storytelling: each subsystem visible in the video; user pacing matches narration |
| API host | **Cloud Run prod** (`mechdesign-backend` service) | Vercel-hosted frontend needs a public backend; localhost fine for dev |
| Backend deploy SA | **`mechdesign-runtime@`** (new) | Cloud Run uses metadata server, no key file; separates dev/prod identities |
| S4 streaming UI | **Visible token-by-token** | "AI writing" visible in video; same SSE infra already used for S1/S2 |
| S5 PDF UX | **Inline iframe preview + 5 download links** | Rubric rewards visible PDF; iframe shows report cover live |
| Languages | **English MVP** (S4 prose); locale toggle only for UI chrome | S4 backend is English-only; bilingual deferred |
| State coordination | **Local `useState` in `/design/page.tsx`** | Pipeline state is page-scoped; Zustand only for cross-page UI (theme/locale) |
| Persistence | **URL query params** (`session_id`, `hash`, future: `analysis_cache_key`, `explain_cache_key`, `document_cache_key`) | Shareable links; cache hits give instant replay |
| Frontend deploy | **Vercel auto-deploy on push** | Already wired; just set `NEXT_PUBLIC_API_URL` env var to Cloud Run URL |
| CORS | **`allow_origin_regex=r"https://.*\.vercel\.app$"`** in FastAPI + GCS bucket CORS allowlist | Vercel preview URLs are dynamic; regex covers them |
| Cache hit retries | **0 server retries; client shows `retry_after` countdown** | Matches backend behavior; explicit user action |
| Mobile | **Best-effort responsive** (3-col → 1-col < 768 px) | Demo will record desktop; mobile is a future polish |

---

## 3. Architecture

Two deploys + one new code module.

```
┌─────────────────────────────────────────────────────────────┐
│  Vercel (frontend)                                           │
│  apps/frontend/  — Next.js 14 App Router, TypeScript strict  │
│  ├ /design       — 3-col + 3 new panels stacked              │
│  ├ /lib/hooks    — +useAnalyze, +useExplainStream, +useDoc.  │
│  └ /components   — +analysis/ +narrative/ +deliverables/     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS, NEXT_PUBLIC_API_URL
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Cloud Run (us-central1, project mechdesign-ai)              │
│  mechdesign-backend — FastAPI, mechdesign-runtime@ SA        │
│  ├ /interpret  /interpret/refine  /generate                  │
│  ├ /analyze    /explain           /document                  │
│  └ CORS: allow_origin_regex=r"https://.*\.vercel\.app$"      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Vertex + GCS + Firestore
                               ▼
                       mechdesign-ai-artifacts (GCS)
                       + Firestore (sessions)
                       + Vertex AI Gemini 2.5 Flash
```

### Three layers in the frontend change

**Hook layer** (`apps/frontend/lib/hooks/`): three new hooks that mirror the existing `useGenerateStream` contract — uniform `{ state, error, run/start, ... }` shape, AbortController for cancellation, no global state. Each wraps `apiPost` (for /analyze, /document — sync JSON) or `apiStream` (for /explain — SSE).

**Component layer** (`apps/frontend/components/`): three new dirs with one Panel each and 1-2 helpers. Panels are presentational; they receive props from the parent page and use their respective hook internally for state. Panels always render an action button + result body, and are disabled until prerequisites are met.

**Page layer** (`apps/frontend/app/design/page.tsx`): the page owns the canonical state — `intent`, `materialName`, `analysis`, `narrative`, `geometryArtifacts`. It threads these as props to the new panels, and each panel calls back with its result so the parent can pass it to the next stage.

### Why this shape

- Per-stage manual triggers mean each panel is **idempotent and independently testable** — you can click Analyze with stale geometry, click Explain twice, etc.
- Local state (no global store) means **panel composition is explicit** — easier to reason about what enables what.
- Mirroring existing `useGenerateStream` shape means **zero conceptual overhead** for the next engineer to add a sixth stage.

---

## 4. Components

### 4.1 `lib/hooks/useAnalyze.ts`

Sync POST /analyze.

```typescript
export type AnalyzeState = 'idle' | 'running' | 'done' | 'error'

export function useAnalyze() {
  const [state, setState] = useState<AnalyzeState>('idle')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(async (intent: DesignIntent, materialName: string) => {
    setState('running'); setError(null); setResult(null)
    try {
      const data = await apiPost<AnalysisResult>('/analyze', {
        intent, material_name: materialName,
      })
      setResult(data); setState('done')
    } catch (e: unknown) {
      setError((e as { body?: BackendError })?.body ?? { code: 'network_error', message: String(e) })
      setState('error')
    }
  }, [])

  return { state, result, error, run }
}
```

### 4.2 `lib/hooks/useExplainStream.ts`

SSE /explain with token accumulation.

```typescript
export type ExplainState = 'idle' | 'streaming' | 'done' | 'error'

export function useExplainStream() {
  const [state, setState] = useState<ExplainState>('idle')
  const [streamedText, setStreamedText] = useState('')
  const [report, setReport] = useState<NaturalReport | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const start = useCallback(async (intent, analysis, sessionId) => {
    setState('streaming'); setStreamedText(''); setReport(null); setError(null)
    try {
      for await (const ev of apiStream('/explain', {
        intent, analysis_result: analysis, session_id: sessionId,
      })) {
        if (ev.event === 'chunk' && typeof ev.data?.text === 'string') {
          setStreamedText(prev => prev + ev.data.text)
        } else if (ev.event === 'final' && ev.data?.report) {
          setReport(ev.data.report as NaturalReport)
        } else if (ev.event === 'error') {
          setError(ev.data as BackendError); setState('error'); return
        }
      }
      setState('done')
    } catch (e) {
      setError({ code: 'network_error', message: String(e) }); setState('error')
    }
  }, [])

  return { state, streamedText, report, error, start }
}
```

### 4.3 `lib/hooks/useDocument.ts`

Sync POST /document.

```typescript
export function useDocument() {
  const [state, setState] = useState<'idle'|'running'|'done'|'error'>('idle')
  const [deliverables, setDeliverables] = useState<Deliverables | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(async (intent, analysis, narrative, geometryArtifacts, sessionId) => {
    setState('running'); setError(null); setDeliverables(null)
    try {
      const data = await apiPost<Deliverables>('/document', {
        intent, analysis_result: analysis, natural_report: narrative,
        geometry_artifacts: geometryArtifacts, session_id: sessionId,
      })
      setDeliverables(data); setState('done')
    } catch (e: unknown) {
      setError((e as { body?: BackendError })?.body ?? { code: 'network_error', message: String(e) })
      setState('error')
    }
  }, [])

  return { state, deliverables, error, run }
}
```

### 4.4 `components/analysis/AnalysisPanel.tsx`

Verdict badge (green/amber/red), SF, formula, stress, displacement.

Key elements: badge color from `COLOR_VERDICT` map (`pass`→emerald, `warn`→amber, `fail`→red), formula in monospace, KV grid for numerics. Action button `Analyze` disabled until `intent && geometryArtifacts`.

### 4.5 `components/narrative/NarrativePanel.tsx`

Streaming text while generating; structured `report` with sections (Summary / Risks / Suggestions / Analogies / Facts cited footer) after final event.

Uses `<pre className="whitespace-pre-wrap">` for streaming text. After final event, renders structured Markdown-like layout from `report` object.

Children:
- `StreamingText.tsx` — small helper that renders text with a blinking cursor while `state === 'streaming'`.

### 4.6 `components/deliverables/DeliverablesPanel.tsx`

5 download links (report, drawing, step, glb, svg) + inline iframe preview of report PDF.

Action button `Generate documents` disabled until `intent && analysis && narrative && geometryArtifacts`. iframe `src={deliverables.report_pdf_url}` with `h-96` height. If iframe fails (CSP / CORS), fallback message "Preview unavailable — open in new tab".

Children:
- `PdfPreview.tsx` — iframe with onError fallback.

### 4.7 `app/design/page.tsx` extensions

State additions:

```tsx
const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
const [narrative, setNarrative] = useState<NaturalReport | null>(null)
const [materialName, setMaterialName] = useState<string>('steel_a36')

const geometryArtifacts = result?.artifacts ?? null   // result from useGenerateStream
```

Layout change: stack new panels under ViewerPanel inside the center column (or below if single-col on mobile).

```
<div className="grid grid-cols-1 md:grid-cols-[280px_1fr_320px] gap-3 h-full">
  <FormPanel ... />
  <div className="space-y-3 overflow-y-auto">
    <ViewerPanel ... />
    <AnalysisPanel intent={intent} materialName={materialName} onResult={setAnalysis} />
    <NarrativePanel intent={intent} analysis={analysis} sessionId={sessionId} onReport={setNarrative} />
    <DeliverablesPanel intent={intent} analysis={analysis} narrative={narrative}
                       geometryArtifacts={geometryArtifacts} sessionId={sessionId} />
  </div>
  <ChatPanel ... />
</div>
```

### 4.8 Types + Zod schemas

`lib/types.ts` additions:

```typescript
export interface AnalysisResult {
  intent_type: string
  material_name: string
  material_yield_mpa: number
  formula: string
  stress_max_pa: number
  displacement_max_m: number
  safety_factor: number
  verdict: 'pass' | 'warn' | 'fail'
  inputs: Record<string, number>
  notes?: string | null
}
export interface NaturalReport {
  summary: string
  risks: string[]
  suggestions: string[]
  analogies: string[]
  facts_used: string[]
}
export interface Deliverables {
  report_pdf_url: string
  drawing_pdf_url: string
  step_url: string
  glb_url: string
  svg_url: string
  cache_hit: boolean
  cache_key: string
}
```

`lib/schemas.ts`: Zod mirrors for runtime validation in `apiPost<T>(... , schema)`.

### 4.9 Backend Dockerfile

`apps/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY apps/backend/pyproject.toml apps/backend/uv.lock* /app/
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY apps/backend /app
ENV PYTHONPATH=/app PORT=8080
EXPOSE 8080
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT}
```

`.dockerignore`:

```
.venv .pytest_cache .ruff_cache .mypy_cache __pycache__
*.pyc tests/ .env* *.md data/demo_artifacts/*
```

### 4.10 Runtime service account

New SA `mechdesign-runtime@mechdesign-ai.iam.gserviceaccount.com`. Roles:
- `roles/storage.objectAdmin` on project (for bucket access)
- `roles/aiplatform.user` on project
- `roles/datastore.user` on project (Firestore sessions)
- `roles/serviceusage.serviceUsageConsumer` on project
- `roles/iam.serviceAccountTokenCreator` on itself (for signed URL signing via IAM API)

Created via the deploy script (`infra/deploy-backend.sh`) — one-time.

### 4.11 `infra/deploy-backend.sh`

End-to-end deploy script (see §3 sketch). Submits build to Cloud Build → image to Artifact Registry → `gcloud run deploy` with all env vars baked into the revision. Idempotent — re-runs deploy a new revision.

### 4.12 CORS update (backend)

`services/interpreter/app.py` currently uses `allow_origins=settings.cors_allowed_origins`. Change to:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,        # exact origins (localhost)
    allow_origin_regex=r"https://.*\.vercel\.app$",     # all Vercel preview/prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4.13 Vercel env

Set in Vercel project dashboard (Settings → Environment Variables):

| Key | Value | Scope |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://mechdesign-backend-<hash>-uc.a.run.app` | Production |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8080` | Development |

### 4.14 GCS bucket CORS

```json
[{
  "origin": ["https://mechdesign.vercel.app", "http://localhost:3000"],
  "method": ["GET","HEAD","OPTIONS"],
  "responseHeader": ["Content-Type","Range"],
  "maxAgeSeconds": 3600
}]
```

Applied via `gcloud storage buckets update gs://mechdesign-ai-artifacts --cors-file=...`.

---

## 5. Data Flow

### 5.1 Happy path (~25 s cold, ~4 s warm)

```
1. User on /design (preset=flywheel | none)
2. Send prompt -> useInterpretStream (~6 s)
   -> ChatPanel streams, FormPanel fills (tri-state)
3. Fill missing fields manually
4. Click Generate -> useGenerateStream (~2-5 s)
   -> ProgressStream shows steps
   -> ViewerPanel loads GLB, MassPanel shows mass + cache_key
5. Click Analyze -> useAnalyze (~50 ms)
   -> AnalysisPanel renders verdict badge + SF + formula
6. Click Explain -> useExplainStream (~6-8 s)
   -> NarrativePanel streamedText grows token-by-token
   -> Final event: structured report renders (Summary / Risks / Suggestions / Analogies)
7. Click Generate documents -> useDocument (~2 s)
   -> DeliverablesPanel: 5 links + iframe preview of report PDF
```

### 5.2 Error paths (frontend behavior)

| Backend error | Frontend UX |
|---|---|
| 422 `invalid_input` | ErrorBanner with `field` + `message` |
| 422 `missing_load_parameter` | Inline message in FormPanel pointing to the missing field |
| 422 `material_not_found` | MaterialSelector shows error state |
| 500 `geometry_rebuild_failed` | "Geometry build failed. Try simpler parameters." + Retry button |
| 502 `gcs_upload_failed` | Countdown using `retry_after`, manual Retry button |
| 504 `gemma_timeout` | "AI assistant is slow today. Retrying in N s." + auto-retry once |
| Network error | Toast "Backend unreachable" |
| SSE disconnect mid-stream | Partial state preserved; "Stream interrupted, retry?" inline |

### 5.3 URL state

| Param | Source | Use |
|---|---|---|
| `session_id` | `getOrCreateSessionId()` | Persists session across reload |
| `preset` | Landing page hero card | Pre-fills FormPanel prompt |
| `hash` | `useGenerateStream` final event | Re-hydrates geometry via `GET /generate/artifacts/{hash}` |
| `analysis_cache_key`, `explain_cache_key`, `document_cache_key` | Each panel's final event | Future: re-hydrate downstream stages (stretch goal — same cache-by-hash backend retrieval) |

### 5.4 HTTP contracts

All five endpoints already documented in their respective specs (S1-S5). Frontend consumes them verbatim. No new backend endpoints required for this work.

---

## 6. Error Handling and Observability UX

### 6.1 Banner system

Reuse existing `ErrorBanner` component. Each new Panel renders an ErrorBanner inline when its hook returns `error`. Banners show:
- `code` (lowercase) as small chip
- `message` as body
- `field` (if present) as muted prefix
- `retry_after` countdown if present, with Retry button after countdown

### 6.2 Loading states

Panel button text changes:
- `Analyze` → `Analyzing…`
- `Explain` → `Explaining…`
- `Generate documents` → `Packaging…`

Disabled state visible (no spinner needed; existing `disabled:opacity-50` style).

Reuse `ProgressStream` from `components/shared/` for SSE-driven progress (already wired for /generate; also applies to /explain).

### 6.3 Console diagnostics

Each hook logs structured console messages prefixed with the endpoint:
```
[analyze] state=running
[analyze] state=done sf=5.16 verdict=pass
[explain] state=streaming chunks=24 totalChars=312
```

Helpful for the demo recording (DevTools open shows the pipeline progressing).

### 6.4 Retry policy

- 422 / `invalid_input`: 0 retries (user fixes input)
- 502 / `gcs_upload_failed`: 0 server retries (backend already retried); frontend exposes Retry after `retry_after`
- 504 / `gemma_timeout`: 1 auto-retry after 5 s; if still fails, manual Retry button

---

## 7. Testing Strategy

### 7.1 Pyramid

| Layer | Type | What it verifies | Count |
|---|---|---|---|
| Unit — hooks | vitest + msw | State transitions, SSE chunk accumulation, error mapping | 12 |
| Unit — components | vitest + React Testing Library | Verdict badge colors, bullets render, panels disabled until ready | 9 |
| Integration — happy path | vitest + msw | /design full flow: 5 panels populate sequentially | 1 |
| E2E | Playwright + msw or live localhost | Full pipeline against running backend | 2 (smoke: localhost + Cloud Run) |

**Total ~24 tests. Suite target < 10 s** with msw.

### 7.2 msw handlers

Three new handlers (sync /analyze, SSE /explain, sync /document) added to `apps/frontend/test/msw/handlers.ts`. SSE handler returns a ReadableStream that emits `chunk` then `final` events with synthetic data matching the production schemas.

### 7.3 Critical tests

- `useExplainStream` accumulates chunks into `streamedText`
- `AnalysisPanel` renders WARN badge with amber color
- `DeliverablesPanel` button disabled until prerequisites met
- Integration: click each button in sequence, assert all panels populate

### 7.4 E2E

`apps/frontend/e2e/full_pipeline.spec.ts`:
1. Navigate to `/design?preset=flywheel`
2. Fill prompt, click Send → wait for FormPanel populated
3. Click Generate → wait for `<canvas>` (R3F viewer mounted)
4. Click Analyze → wait for verdict text (PASS|WARN|FAIL)
5. Click Explain → wait for "Facts cited:" footer
6. Click Generate documents → wait for `iframe[title="report preview"]`

Two variants: msw-mocked (CI) and live-backend (manual pre-demo against Cloud Run).

### 7.5 Coverage gate

≥ 70% in `apps/frontend/lib/hooks/` + `apps/frontend/components/{analysis,narrative,deliverables}/`. Lower than backend's 85% because UI tests are inherently more flaky (timing, DOM specifics).

---

## 8. Acceptance Criteria

**Functional**:
- [ ] `/design` shows 6 panels: FormPanel, ChatPanel, ViewerPanel, AnalysisPanel, NarrativePanel, DeliverablesPanel
- [ ] Three new hooks present and used: `useAnalyze`, `useExplainStream`, `useDocument`
- [ ] NarrativePanel streams `streamedText` token-by-token; renders structured report after final event
- [ ] DeliverablesPanel displays 5 URLs + iframe preview of report PDF
- [ ] Each panel's Action button disabled until its prerequisites are met; tooltip explains why
- [ ] All backend errors surface via ErrorBanner with code + message + optional field/retry_after
- [ ] Backend deployed to Cloud Run service `mechdesign-backend` in `us-central1`
- [ ] `mechdesign-runtime@` SA configured with required roles
- [ ] Backend CORS uses `allow_origin_regex` matching Vercel domains
- [ ] GCS bucket CORS allows Vercel + localhost
- [ ] Frontend `NEXT_PUBLIC_API_URL` set in Vercel for production scope
- [ ] Frontend deploys to Vercel on push

**Non-functional**:
- [ ] Cache hit re-runs of /generate /analyze /document < 500 ms each
- [ ] /explain p95 < 10 s (Gemini 2.5 Flash streaming)
- [ ] Total pipeline cold latency: first click → final iframe < 25 s
- [ ] Best-effort mobile: 3-col layout collapses < 768 px
- [ ] No console errors during demo run

**Quality**:
- [ ] TypeScript strict, no `any` in new files (except narrow `as unknown as ...` casts)
- [ ] All new hooks return uniform `{ state, error, ... }`
- [ ] All new components reuse existing UI primitives
- [ ] Zod schemas in `lib/schemas.ts` for `AnalysisResult`, `NaturalReport`, `Deliverables`
- [ ] Coverage ≥ 70% in new code

**Documentation**:
- [ ] `apps/frontend/README.md` lists new endpoints and Vercel env vars
- [ ] This spec doc committed
- [ ] Plan doc at `docs/superpowers/plans/2026-05-16-frontend-wiring.md`
- [ ] `infra/deploy-backend.sh` script committed and runnable

---

## 9. Demo Script

```
0:00-0:05  Open /design?preset=flywheel
           Hero prompt pre-fills FormPanel.

0:05-0:12  Click Send. Chat panel streams "Interpreting...".
           FormPanel fills tri-state fields (rpm extracted, dimensions missing).

0:12-0:18  User fills missing dimensions. Click Generate.
           ProgressStream shows progress; ViewerPanel boots R3F, GLB loads.
           MassPanel shows mass + cache_key.

0:18-0:20  Click Analyze. Verdict badge (PASS/WARN/FAIL), SF, formula appear.

0:20-0:28  Click Explain. NaturalReport text streams token-by-token.
           Final event: structured panel with Summary/Risks/Suggestions/Analogies.
           Footer: "Facts cited: stress_max_mpa, safety_factor, ..."

0:28-0:35  Click Generate documents. PDF preview iframe loads in DeliverablesPanel.
           5 download links visible. Voice-over: "Every number on the PDF came
           from the analyzer; the narrative came from a grounded LLM; nothing invented."

0:35-0:45  Switch tab to /design?preset=hydro. Repeat compressed view (cache hits).
           Switch to /design?preset=shelter.
```

If the design does not support this flow, the design is wrong.

---

## 10. Open Questions

None at approval time. All decisions (scope, triggers, hosts, streaming UX, PDF UX, deploys, CORS) are confirmed.

---

## 11. Next Step

Invoke `superpowers:writing-plans` to decompose this spec into an implementation plan.
