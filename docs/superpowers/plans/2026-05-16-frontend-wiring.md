# Frontend Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `/design` page with per-stage UI for S3 / S4 / S5, deploy backend to Cloud Run, and point the Vercel-hosted frontend at it so the full pipeline (S1→S2→S3→S4→S5) is visible in the demo video.

**Architecture:** Three new hooks mirroring `useGenerateStream` shape, three new component dirs (analysis, narrative, deliverables) stacked under the existing center column, page-level state coordinates the pipeline. Backend ships as a Cloud Run service (`mechdesign-backend`) with a dedicated runtime service account.

**Tech Stack:** Next.js 14 App Router, TypeScript strict, vitest + React Testing Library + msw, Playwright, Zustand (existing, untouched), Cloud Run, Cloud Build, Artifact Registry, FastAPI CORSMiddleware.

**Spec:** `docs/superpowers/specs/2026-05-16-frontend-wiring-design.md`

---

## Pre-flight

All commands run from the repo root (`/Users/cristhianrodriguez/repositories/googlemind_workspace`) unless stated otherwise. Frontend commands: `cd apps/frontend && npm run …` or `npm exec …`. Backend Docker / Cloud Run commands assume `gcloud auth login` is active with `cristhianrodriguez.dev@gmail.com` and `gcloud config get-value project` returns `mechdesign-ai`.

Conventional commits, no `Co-Authored-By`, no `--no-verify`. The repo branch is `master` (user-consented direct commits).

Existing test infrastructure: vitest with `environment: 'jsdom'`, `@testing-library/jest-dom/vitest` imported in `apps/frontend/test/setup.ts`, msw `server` in `apps/frontend/test/msw/server.ts`. Run a single test file with `npm run test -- path/to/file.test.ts`.

---

## File Structure

**Created**:

```
apps/frontend/
├── lib/
│   ├── hooks/
│   │   ├── useAnalyze.ts                    # sync POST /analyze
│   │   ├── useAnalyze.test.tsx
│   │   ├── useExplainStream.ts              # SSE POST /explain
│   │   ├── useExplainStream.test.tsx
│   │   ├── useDocument.ts                   # sync POST /document
│   │   └── useDocument.test.tsx
│   └── (types.ts and schemas.ts modified — see below)
├── components/
│   ├── analysis/
│   │   ├── AnalysisPanel.tsx
│   │   └── AnalysisPanel.test.tsx
│   ├── narrative/
│   │   ├── NarrativePanel.tsx
│   │   ├── NarrativePanel.test.tsx
│   │   └── StreamingText.tsx
│   └── deliverables/
│       ├── DeliverablesPanel.tsx
│       ├── DeliverablesPanel.test.tsx
│       └── PdfPreview.tsx
├── test/
│   └── integration/
│       └── full_pipeline.test.tsx           # vitest integration
└── e2e/
    └── full_pipeline.spec.ts                # Playwright

apps/backend/
├── Dockerfile
└── .dockerignore

infra/
└── deploy-backend.sh                        # (already exists; REPLACED)
```

**Modified**:

- `apps/frontend/lib/types.ts` — add `AnalysisResult`, `NaturalReport`, `Deliverables`, `CachedArtifacts` interfaces
- `apps/frontend/lib/schemas.ts` — add Zod mirrors for runtime validation
- `apps/frontend/test/msw/handlers.ts` — add `/analyze`, `/explain`, `/document` handlers
- `apps/frontend/app/design/page.tsx` — add state + mount three new panels under ViewerPanel
- `apps/frontend/README.md` — document new env var and endpoints
- `apps/backend/services/interpreter/app.py` — add `allow_origin_regex` to CORSMiddleware

---

## Task 1: Types + Zod schemas

**Files:**
- Modify: `apps/frontend/lib/types.ts`
- Modify: `apps/frontend/lib/schemas.ts`
- Test: `apps/frontend/lib/schemas.test.ts` (existing file — extend)

- [ ] **Step 1: Inspect existing types and schemas**

Run: `wc -l apps/frontend/lib/types.ts apps/frontend/lib/schemas.ts apps/frontend/lib/schemas.test.ts`

This tells you where to append. Read the bottom of each so the new types follow the existing naming and export style (camelCase or PascalCase, single export per type, etc.).

- [ ] **Step 2: Write failing schema test** — append at the end of `apps/frontend/lib/schemas.test.ts`

```typescript
import { describe, expect, it } from 'vitest'
import {
  analysisResultSchema,
  naturalReportSchema,
  deliverablesSchema,
} from './schemas'

describe('analysisResultSchema', () => {
  it('accepts a valid result', () => {
    const ok = analysisResultSchema.parse({
      intent_type: 'Flywheel_Rim',
      material_name: 'steel_a36',
      material_yield_mpa: 250,
      formula: 'sigma = rho*omega^2*R^2',
      stress_max_pa: 1.93e8,
      displacement_max_m: 4.84e-4,
      safety_factor: 1.29,
      verdict: 'warn',
      inputs: { angular_velocity_rad_s: 314.16 },
      notes: null,
    })
    expect(ok.verdict).toBe('warn')
  })

  it('rejects an unknown verdict', () => {
    expect(() =>
      analysisResultSchema.parse({
        intent_type: 'Flywheel_Rim', material_name: 'steel_a36',
        material_yield_mpa: 250, formula: 'x',
        stress_max_pa: 0, displacement_max_m: 0,
        safety_factor: 0, verdict: 'oops', inputs: {},
      }),
    ).toThrow()
  })
})

describe('naturalReportSchema', () => {
  it('defaults missing lists to empty', () => {
    const r = naturalReportSchema.parse({ summary: 'ok' })
    expect(r.risks).toEqual([])
    expect(r.suggestions).toEqual([])
    expect(r.analogies).toEqual([])
    expect(r.facts_used).toEqual([])
  })
})

describe('deliverablesSchema', () => {
  it('requires the five URLs and cache fields', () => {
    const d = deliverablesSchema.parse({
      report_pdf_url: 'a', drawing_pdf_url: 'b',
      step_url: 'c', glb_url: 'd', svg_url: 'e',
      cache_hit: true, cache_key: 'abc',
    })
    expect(d.cache_hit).toBe(true)
  })
})
```

- [ ] **Step 3: Run test, confirm FAIL**

Run from `apps/frontend/`:
```bash
npm test -- lib/schemas.test.ts
```
Expected: 3 new tests fail with `analysisResultSchema is not defined` (or similar).

- [ ] **Step 4: Add types to `apps/frontend/lib/types.ts`**

Append at the end of the file:

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

If `CachedArtifacts` is not already present in `types.ts` (check via `grep -n "CachedArtifacts" apps/frontend/lib/types.ts`), also add:

```typescript
export interface MassProperties {
  volume_m3: number
  mass_kg: number
  center_of_mass: [number, number, number]
  bbox_m: [number, number, number, number, number, number]
}

export interface CachedArtifacts {
  mass_properties: MassProperties
  step_url: string
  glb_url: string
  svg_url: string
}
```

- [ ] **Step 5: Add Zod schemas to `apps/frontend/lib/schemas.ts`**

Append at the end of the file:

```typescript
import { z } from 'zod'

export const analysisResultSchema = z.object({
  intent_type: z.string(),
  material_name: z.string(),
  material_yield_mpa: z.number(),
  formula: z.string(),
  stress_max_pa: z.number(),
  displacement_max_m: z.number(),
  safety_factor: z.number(),
  verdict: z.enum(['pass', 'warn', 'fail']),
  inputs: z.record(z.string(), z.number()),
  notes: z.string().nullable().optional(),
})

export const naturalReportSchema = z.object({
  summary: z.string(),
  risks: z.array(z.string()).default([]),
  suggestions: z.array(z.string()).default([]),
  analogies: z.array(z.string()).default([]),
  facts_used: z.array(z.string()).default([]),
})

export const deliverablesSchema = z.object({
  report_pdf_url: z.string(),
  drawing_pdf_url: z.string(),
  step_url: z.string(),
  glb_url: z.string(),
  svg_url: z.string(),
  cache_hit: z.boolean(),
  cache_key: z.string(),
})
```

If the existing `schemas.ts` does not already `import { z } from 'zod'` at the top, do not duplicate the import; only append the new exports.

- [ ] **Step 6: Run tests, confirm PASS**

Run from `apps/frontend/`:
```bash
npm test -- lib/schemas.test.ts
```
Expected: all tests pass (existing + 3 new).

- [ ] **Step 7: Verify TypeScript clean**

Run from `apps/frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add apps/frontend/lib/types.ts apps/frontend/lib/schemas.ts apps/frontend/lib/schemas.test.ts
git commit -m "feat(frontend): add AnalysisResult, NaturalReport, Deliverables types + schemas"
```

---

## Task 2: useAnalyze hook

**Files:**
- Create: `apps/frontend/lib/hooks/useAnalyze.ts`
- Create: `apps/frontend/lib/hooks/useAnalyze.test.tsx`

- [ ] **Step 1: Write failing test** — `apps/frontend/lib/hooks/useAnalyze.test.tsx`

```typescript
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type { DesignIntent } from '../types'
import { useAnalyze } from './useAnalyze'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: {
    outer_diameter_m: { value: 0.5, source: 'extracted' },
    inner_diameter_m: { value: 0.1, source: 'extracted' },
    thickness_m: { value: 0.05, source: 'extracted' },
    rpm: { value: 3000, source: 'extracted' },
  },
  composed_of: [],
}

const ANALYSIS_RESULT = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'sigma = rho*omega^2*R^2',
  stress_max_pa: 4.84e7,
  displacement_max_m: 6e-5,
  safety_factor: 5.16,
  verdict: 'pass',
  inputs: { angular_velocity_rad_s: 314.16 },
  notes: null,
}

describe('useAnalyze', () => {
  it('transitions idle -> running -> done and sets result', async () => {
    server.use(
      http.post('*/analyze', () => HttpResponse.json(ANALYSIS_RESULT)),
    )
    const { result } = renderHook(() => useAnalyze())
    expect(result.current.state).toBe('idle')
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.result?.verdict).toBe('pass')
    expect(result.current.result?.safety_factor).toBe(5.16)
  })

  it('transitions idle -> running -> error on 422', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'invalid_input', message: 'bad', field: 'material_name' },
          { status: 422 },
        ),
      ),
    )
    const { result } = renderHook(() => useAnalyze())
    await act(async () => {
      await result.current.run(INTENT, 'unobtanium')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('invalid_input')
    expect(result.current.error?.field).toBe('material_name')
  })

  it('clears prior result when run is called again', async () => {
    server.use(http.post('*/analyze', () => HttpResponse.json(ANALYSIS_RESULT)))
    const { result } = renderHook(() => useAnalyze())
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'unknown', message: 'boom' },
          { status: 500 },
        ),
      ),
    )
    await act(async () => {
      await result.current.run(INTENT, 'steel_a36')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.result).toBeNull()
  })
})
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- lib/hooks/useAnalyze.test.tsx
```
Expected: cannot find module `./useAnalyze`.

- [ ] **Step 3: Write production code** — `apps/frontend/lib/hooks/useAnalyze.ts`

```typescript
'use client'
import { useCallback, useState } from 'react'
import { apiPost } from '@/lib/api-client'
import type { AnalysisResult, BackendError, DesignIntent } from '@/lib/types'

export type AnalyzeState = 'idle' | 'running' | 'done' | 'error'

export function useAnalyze() {
  const [state, setState] = useState<AnalyzeState>('idle')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(
    async (intent: DesignIntent, materialName: string) => {
      setState('running')
      setError(null)
      setResult(null)
      try {
        const data = await apiPost<AnalysisResult>('/analyze', {
          intent,
          material_name: materialName,
        })
        setResult(data)
        setState('done')
      } catch (e: unknown) {
        const body = (e as { body?: BackendError }).body
        setError(body ?? { code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, result, error, run }
}
```

- [ ] **Step 4: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- lib/hooks/useAnalyze.test.tsx
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/lib/hooks/useAnalyze.ts apps/frontend/lib/hooks/useAnalyze.test.tsx
git commit -m "feat(frontend): add useAnalyze hook for sync POST /analyze"
```

---

## Task 3: useExplainStream hook

**Files:**
- Create: `apps/frontend/lib/hooks/useExplainStream.ts`
- Create: `apps/frontend/lib/hooks/useExplainStream.test.tsx`

- [ ] **Step 1: Write failing test** — `apps/frontend/lib/hooks/useExplainStream.test.tsx`

```typescript
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type { AnalysisResult, DesignIntent } from '../types'
import { useExplainStream } from './useExplainStream'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'sigma = rho*omega^2*R^2',
  stress_max_pa: 4.84e7,
  displacement_max_m: 6e-5,
  safety_factor: 5.16,
  verdict: 'pass',
  inputs: {},
}

const SSE_OK = [
  { event: 'chunk', data: { text: 'The ' } },
  { event: 'chunk', data: { text: 'flywheel ' } },
  { event: 'chunk', data: { text: 'looks good.' } },
  {
    event: 'final',
    data: {
      report: {
        summary: 'The flywheel looks good.',
        risks: [],
        suggestions: [],
        analogies: [],
        facts_used: ['safety_factor'],
      },
      cache_hit: false,
      cache_key: 'abc',
    },
  },
]

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('')
}

describe('useExplainStream', () => {
  it('accumulates chunk text and emits final report', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(sseBody(SSE_OK), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    )
    const { result } = renderHook(() => useExplainStream())
    await act(async () => {
      await result.current.start(INTENT, ANALYSIS, 'sid-1')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.streamedText).toBe('The flywheel looks good.')
    expect(result.current.report?.summary).toBe('The flywheel looks good.')
    expect(result.current.report?.facts_used).toEqual(['safety_factor'])
  })

  it('transitions to error when SSE emits an error event', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(
          sseBody([
            { event: 'progress', data: { step: 'generating' } },
            {
              event: 'error',
              data: { code: 'gemma_timeout', message: 'slow', retry_after: 5 },
            },
          ]),
          { headers: { 'Content-Type': 'text/event-stream' } },
        ),
      ),
    )
    const { result } = renderHook(() => useExplainStream())
    await act(async () => {
      await result.current.start(INTENT, ANALYSIS, 'sid-1')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('gemma_timeout')
  })
})
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- lib/hooks/useExplainStream.test.tsx
```
Expected: cannot find module.

- [ ] **Step 3: Write production code** — `apps/frontend/lib/hooks/useExplainStream.ts`

```typescript
'use client'
import { useCallback, useState } from 'react'
import { apiStream } from '@/lib/api-client'
import type {
  AnalysisResult,
  BackendError,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export type ExplainState = 'idle' | 'streaming' | 'done' | 'error'

export function useExplainStream() {
  const [state, setState] = useState<ExplainState>('idle')
  const [streamedText, setStreamedText] = useState('')
  const [report, setReport] = useState<NaturalReport | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const start = useCallback(
    async (
      intent: DesignIntent,
      analysis: AnalysisResult,
      sessionId: string | null,
    ) => {
      setState('streaming')
      setStreamedText('')
      setReport(null)
      setError(null)
      try {
        for await (const ev of apiStream('/explain', {
          intent,
          analysis_result: analysis,
          session_id: sessionId,
        })) {
          if (ev.event === 'chunk' && typeof (ev.data as { text?: string }).text === 'string') {
            const text = (ev.data as { text: string }).text
            setStreamedText((prev) => prev + text)
          } else if (ev.event === 'final' && (ev.data as { report?: NaturalReport }).report) {
            setReport((ev.data as { report: NaturalReport }).report)
          } else if (ev.event === 'error') {
            setError(ev.data as BackendError)
            setState('error')
            return
          }
        }
        setState('done')
      } catch (e: unknown) {
        setError({ code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, streamedText, report, error, start }
}
```

- [ ] **Step 4: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- lib/hooks/useExplainStream.test.tsx
```
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/lib/hooks/useExplainStream.ts apps/frontend/lib/hooks/useExplainStream.test.tsx
git commit -m "feat(frontend): add useExplainStream hook for SSE POST /explain"
```

---

## Task 4: useDocument hook

**Files:**
- Create: `apps/frontend/lib/hooks/useDocument.ts`
- Create: `apps/frontend/lib/hooks/useDocument.test.tsx`

- [ ] **Step 1: Write failing test** — `apps/frontend/lib/hooks/useDocument.test.tsx`

```typescript
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '../types'
import { useDocument } from './useDocument'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}
const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'x',
  stress_max_pa: 1,
  displacement_max_m: 1,
  safety_factor: 5,
  verdict: 'pass',
  inputs: {},
}
const NARRATIVE: NaturalReport = {
  summary: 'ok', risks: [], suggestions: [], analogies: [], facts_used: ['safety_factor'],
}
const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75, center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://example/step',
  glb_url: 'https://example/glb',
  svg_url: 'https://example/svg',
}

const DELIVERABLES = {
  report_pdf_url: 'https://example/report.pdf',
  drawing_pdf_url: 'https://example/drawing.pdf',
  step_url: 'https://example/step',
  glb_url: 'https://example/glb',
  svg_url: 'https://example/svg',
  cache_hit: false,
  cache_key: 'doc1',
}

describe('useDocument', () => {
  it('sets deliverables on success', async () => {
    server.use(http.post('*/document', () => HttpResponse.json(DELIVERABLES)))
    const { result } = renderHook(() => useDocument())
    await act(async () => {
      await result.current.run(INTENT, ANALYSIS, NARRATIVE, ARTIFACTS, 'sid')
    })
    await waitFor(() => expect(result.current.state).toBe('done'))
    expect(result.current.deliverables?.report_pdf_url).toBe('https://example/report.pdf')
  })

  it('sets error on backend 502', async () => {
    server.use(
      http.post('*/document', () =>
        HttpResponse.json(
          { code: 'gcs_upload_failed', message: 'transient', retry_after: 5 },
          { status: 502 },
        ),
      ),
    )
    const { result } = renderHook(() => useDocument())
    await act(async () => {
      await result.current.run(INTENT, ANALYSIS, NARRATIVE, ARTIFACTS, 'sid')
    })
    await waitFor(() => expect(result.current.state).toBe('error'))
    expect(result.current.error?.code).toBe('gcs_upload_failed')
  })
})
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- lib/hooks/useDocument.test.tsx
```
Expected: cannot find module.

- [ ] **Step 3: Write production code** — `apps/frontend/lib/hooks/useDocument.ts`

```typescript
'use client'
import { useCallback, useState } from 'react'
import { apiPost } from '@/lib/api-client'
import type {
  AnalysisResult,
  BackendError,
  CachedArtifacts,
  Deliverables,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export type DocumentState = 'idle' | 'running' | 'done' | 'error'

export function useDocument() {
  const [state, setState] = useState<DocumentState>('idle')
  const [deliverables, setDeliverables] = useState<Deliverables | null>(null)
  const [error, setError] = useState<BackendError | null>(null)

  const run = useCallback(
    async (
      intent: DesignIntent,
      analysis: AnalysisResult,
      narrative: NaturalReport,
      geometryArtifacts: CachedArtifacts,
      sessionId: string | null,
    ) => {
      setState('running')
      setError(null)
      setDeliverables(null)
      try {
        const data = await apiPost<Deliverables>('/document', {
          intent,
          analysis_result: analysis,
          natural_report: narrative,
          geometry_artifacts: geometryArtifacts,
          session_id: sessionId,
        })
        setDeliverables(data)
        setState('done')
      } catch (e: unknown) {
        const body = (e as { body?: BackendError }).body
        setError(body ?? { code: 'network_error', message: String(e) })
        setState('error')
      }
    },
    [],
  )

  return { state, deliverables, error, run }
}
```

- [ ] **Step 4: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- lib/hooks/useDocument.test.tsx
```
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/lib/hooks/useDocument.ts apps/frontend/lib/hooks/useDocument.test.tsx
git commit -m "feat(frontend): add useDocument hook for sync POST /document"
```

---

## Task 5: AnalysisPanel component

**Files:**
- Create: `apps/frontend/components/analysis/AnalysisPanel.tsx`
- Create: `apps/frontend/components/analysis/AnalysisPanel.test.tsx`

- [ ] **Step 1: Write failing test** — `apps/frontend/components/analysis/AnalysisPanel.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../../test/msw/server'
import type { DesignIntent } from '../../lib/types'
import { AnalysisPanel } from './AnalysisPanel'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

describe('AnalysisPanel', () => {
  it('disables the button when intent is null', () => {
    render(<AnalysisPanel intent={null} materialName="steel_a36" onResult={vi.fn()} />)
    expect(screen.getByRole('button', { name: /analyze/i })).toBeDisabled()
  })

  it('shows verdict and SF after clicking Analyze', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json({
          intent_type: 'Flywheel_Rim',
          material_name: 'steel_a36',
          material_yield_mpa: 250,
          formula: 'sigma = rho*omega^2*R^2',
          stress_max_pa: 4.84e7,
          displacement_max_m: 6e-5,
          safety_factor: 5.16,
          verdict: 'pass',
          inputs: {},
          notes: null,
        }),
      ),
    )
    const onResult = vi.fn()
    render(<AnalysisPanel intent={INTENT} materialName="steel_a36" onResult={onResult} />)
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText('PASS')).toBeInTheDocument())
    expect(screen.getByText(/SF = 5\.16/)).toBeInTheDocument()
    expect(screen.getByText('sigma = rho*omega^2*R^2')).toBeInTheDocument()
    await waitFor(() => expect(onResult).toHaveBeenCalled())
  })

  it('shows error message when backend returns 422', async () => {
    server.use(
      http.post('*/analyze', () =>
        HttpResponse.json(
          { code: 'invalid_input', message: 'unknown material', field: 'material_name' },
          { status: 422 },
        ),
      ),
    )
    render(<AnalysisPanel intent={INTENT} materialName="x" onResult={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText(/unknown material/)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- components/analysis/AnalysisPanel.test.tsx
```
Expected: module not found.

- [ ] **Step 3: Write production code** — `apps/frontend/components/analysis/AnalysisPanel.tsx`

```tsx
'use client'
import { useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useAnalyze } from '@/lib/hooks/useAnalyze'
import type { AnalysisResult, DesignIntent } from '@/lib/types'

const VERDICT_COLOR: Record<string, string> = {
  pass: 'bg-emerald-600',
  warn: 'bg-amber-500',
  fail: 'bg-red-600',
}

export interface AnalysisPanelProps {
  intent: DesignIntent | null
  materialName: string
  onResult: (r: AnalysisResult) => void
}

export function AnalysisPanel({ intent, materialName, onResult }: AnalysisPanelProps) {
  const { state, result, error, run } = useAnalyze()

  useEffect(() => {
    if (result) onResult(result)
  }, [result, onResult])

  const handleClick = () => {
    if (intent) void run(intent, materialName)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Structural Analysis</h2>
        <Button
          size="sm"
          disabled={!intent || state === 'running'}
          onClick={handleClick}
        >
          {state === 'running' ? 'Analyzing…' : 'Analyze'}
        </Button>
      </div>
      {error && (
        <div className="text-xs text-red-600">
          {error.field && <span className="font-mono mr-1">[{error.field}]</span>}
          {error.message}
        </div>
      )}
      {result && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 text-xs font-bold text-white rounded ${
                VERDICT_COLOR[result.verdict] ?? 'bg-gray-500'
              }`}
            >
              {result.verdict.toUpperCase()}
            </span>
            <span className="text-sm">SF = {result.safety_factor.toFixed(2)}</span>
          </div>
          <dl className="text-xs grid grid-cols-2 gap-1">
            <dt className="text-muted-foreground">Stress max</dt>
            <dd>{(result.stress_max_pa / 1e6).toFixed(2)} MPa</dd>
            <dt className="text-muted-foreground">Yield</dt>
            <dd>{result.material_yield_mpa.toFixed(1)} MPa</dd>
            <dt className="text-muted-foreground">Displacement</dt>
            <dd>{(result.displacement_max_m * 1000).toFixed(3)} mm</dd>
          </dl>
          <code className="block text-xs bg-muted/50 px-2 py-1 rounded">
            {result.formula}
          </code>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 4: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- components/analysis/AnalysisPanel.test.tsx
```
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/frontend/components/analysis/AnalysisPanel.tsx apps/frontend/components/analysis/AnalysisPanel.test.tsx
git commit -m "feat(frontend): add AnalysisPanel component"
```

---

## Task 6: NarrativePanel + StreamingText

**Files:**
- Create: `apps/frontend/components/narrative/StreamingText.tsx`
- Create: `apps/frontend/components/narrative/NarrativePanel.tsx`
- Create: `apps/frontend/components/narrative/NarrativePanel.test.tsx`

- [ ] **Step 1: Write StreamingText helper** — `apps/frontend/components/narrative/StreamingText.tsx`

```tsx
'use client'

export function StreamingText({ text }: { text: string }) {
  return (
    <pre className="text-xs whitespace-pre-wrap text-muted-foreground">
      {text}
      <span className="inline-block w-2 h-3 bg-current animate-pulse ml-0.5 align-middle" />
    </pre>
  )
}
```

- [ ] **Step 2: Write failing test** — `apps/frontend/components/narrative/NarrativePanel.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../../test/msw/server'
import type { AnalysisResult, DesignIntent } from '../../lib/types'
import { NarrativePanel } from './NarrativePanel'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}
const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'x',
  stress_max_pa: 1,
  displacement_max_m: 1,
  safety_factor: 5,
  verdict: 'pass',
  inputs: {},
}

function sseBody(events: Array<{ event: string; data: unknown }>): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('')
}

describe('NarrativePanel', () => {
  it('disables Explain when analysis is null', () => {
    render(<NarrativePanel intent={INTENT} analysis={null} sessionId={null} onReport={vi.fn()} />)
    expect(screen.getByRole('button', { name: /explain/i })).toBeDisabled()
  })

  it('renders structured report after streaming completes', async () => {
    server.use(
      http.post('*/explain', () =>
        new HttpResponse(
          sseBody([
            { event: 'chunk', data: { text: 'Hello ' } },
            { event: 'chunk', data: { text: 'world.' } },
            {
              event: 'final',
              data: {
                report: {
                  summary: 'Hello world.',
                  risks: ['stress'],
                  suggestions: ['inspect'],
                  analogies: ['like a tiger'],
                  facts_used: ['safety_factor'],
                },
                cache_hit: false,
                cache_key: 'k1',
              },
            },
          ]),
          { headers: { 'Content-Type': 'text/event-stream' } },
        ),
      ),
    )
    const onReport = vi.fn()
    render(
      <NarrativePanel
        intent={INTENT}
        analysis={ANALYSIS}
        sessionId="sid"
        onReport={onReport}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /explain/i }))
    await waitFor(() => expect(screen.getByText('Hello world.')).toBeInTheDocument())
    expect(screen.getByText('stress')).toBeInTheDocument()
    expect(screen.getByText('inspect')).toBeInTheDocument()
    expect(screen.getByText('like a tiger')).toBeInTheDocument()
    expect(screen.getByText(/safety_factor/)).toBeInTheDocument()
    expect(onReport).toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- components/narrative/NarrativePanel.test.tsx
```
Expected: module not found.

- [ ] **Step 4: Write production code** — `apps/frontend/components/narrative/NarrativePanel.tsx`

```tsx
'use client'
import { useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useExplainStream } from '@/lib/hooks/useExplainStream'
import { StreamingText } from './StreamingText'
import type { AnalysisResult, DesignIntent, NaturalReport } from '@/lib/types'

export interface NarrativePanelProps {
  intent: DesignIntent | null
  analysis: AnalysisResult | null
  sessionId: string | null
  onReport: (r: NaturalReport) => void
}

export function NarrativePanel({
  intent,
  analysis,
  sessionId,
  onReport,
}: NarrativePanelProps) {
  const { state, streamedText, report, error, start } = useExplainStream()
  const ready = Boolean(intent && analysis)

  useEffect(() => {
    if (report) onReport(report)
  }, [report, onReport])

  const handleClick = () => {
    if (intent && analysis) void start(intent, analysis, sessionId)
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Engineering Narrative</h2>
        <Button
          size="sm"
          disabled={!ready || state === 'streaming'}
          onClick={handleClick}
        >
          {state === 'streaming' ? 'Explaining…' : 'Explain'}
        </Button>
      </div>
      {error && (
        <div className="text-xs text-red-600">{error.message}</div>
      )}
      {state === 'streaming' && streamedText && !report && (
        <StreamingText text={streamedText} />
      )}
      {report && (
        <div className="space-y-2 text-sm">
          <p>{report.summary}</p>
          {report.risks.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Risks</h3>
              <ul className="text-xs list-disc pl-4">
                {report.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {report.suggestions.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Suggestions</h3>
              <ul className="text-xs list-disc pl-4">
                {report.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {report.analogies.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold mt-2">Analogies</h3>
              <ul className="text-xs list-disc pl-4">
                {report.analogies.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-[10px] text-muted-foreground mt-2">
            Facts cited: {report.facts_used.join(', ')}
          </div>
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 5: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- components/narrative/NarrativePanel.test.tsx
```
Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/frontend/components/narrative/
git commit -m "feat(frontend): add NarrativePanel + StreamingText with SSE token streaming"
```

---

## Task 7: DeliverablesPanel + PdfPreview

**Files:**
- Create: `apps/frontend/components/deliverables/PdfPreview.tsx`
- Create: `apps/frontend/components/deliverables/DeliverablesPanel.tsx`
- Create: `apps/frontend/components/deliverables/DeliverablesPanel.test.tsx`

- [ ] **Step 1: Write PdfPreview helper** — `apps/frontend/components/deliverables/PdfPreview.tsx`

```tsx
'use client'
import { useState } from 'react'

export function PdfPreview({ url, title }: { url: string; title: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return (
      <div className="text-xs text-muted-foreground">
        Preview unavailable.{' '}
        <a href={url} target="_blank" rel="noopener" className="underline">
          Open PDF in new tab
        </a>
      </div>
    )
  }
  return (
    <iframe
      src={url}
      className="w-full h-96 border rounded"
      title={title}
      onError={() => setFailed(true)}
    />
  )
}
```

- [ ] **Step 2: Write failing test** — `apps/frontend/components/deliverables/DeliverablesPanel.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../../test/msw/server'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '../../lib/types'
import { DeliverablesPanel } from './DeliverablesPanel'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}
const ANALYSIS: AnalysisResult = {
  intent_type: 'Flywheel_Rim',
  material_name: 'steel_a36',
  material_yield_mpa: 250,
  formula: 'x',
  stress_max_pa: 1,
  displacement_max_m: 1,
  safety_factor: 5,
  verdict: 'pass',
  inputs: {},
}
const NARRATIVE: NaturalReport = {
  summary: 'ok', risks: [], suggestions: [], analogies: [], facts_used: [],
}
const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75,
    center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://example.com/step',
  glb_url: 'https://example.com/glb',
  svg_url: 'https://example.com/svg',
}

describe('DeliverablesPanel', () => {
  it('disables button until all prerequisites are present', () => {
    render(
      <DeliverablesPanel
        intent={null}
        analysis={null}
        narrative={null}
        geometryArtifacts={null}
        sessionId={null}
      />,
    )
    expect(screen.getByRole('button', { name: /generate documents/i })).toBeDisabled()
  })

  it('renders 5 links and an iframe preview after success', async () => {
    server.use(
      http.post('*/document', () =>
        HttpResponse.json({
          report_pdf_url: 'https://example.com/report.pdf',
          drawing_pdf_url: 'https://example.com/drawing.pdf',
          step_url: 'https://example.com/step',
          glb_url: 'https://example.com/glb',
          svg_url: 'https://example.com/svg',
          cache_hit: false,
          cache_key: 'doc1',
        }),
      ),
    )
    render(
      <DeliverablesPanel
        intent={INTENT}
        analysis={ANALYSIS}
        narrative={NARRATIVE}
        geometryArtifacts={ARTIFACTS}
        sessionId="sid"
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /generate documents/i }))
    await waitFor(() => expect(screen.getByText('Report PDF')).toBeInTheDocument())
    expect(screen.getByText('Drawing PDF')).toBeInTheDocument()
    expect(screen.getByText('STEP')).toBeInTheDocument()
    expect(screen.getByText('GLB')).toBeInTheDocument()
    expect(screen.getByText('SVG section')).toBeInTheDocument()
    expect(screen.getByTitle(/report preview/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run, confirm FAIL**

```bash
cd apps/frontend && npm test -- components/deliverables/DeliverablesPanel.test.tsx
```
Expected: module not found.

- [ ] **Step 4: Write production code** — `apps/frontend/components/deliverables/DeliverablesPanel.tsx`

```tsx
'use client'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useDocument } from '@/lib/hooks/useDocument'
import { PdfPreview } from './PdfPreview'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'

export interface DeliverablesPanelProps {
  intent: DesignIntent | null
  analysis: AnalysisResult | null
  narrative: NaturalReport | null
  geometryArtifacts: CachedArtifacts | null
  sessionId: string | null
}

export function DeliverablesPanel({
  intent,
  analysis,
  narrative,
  geometryArtifacts,
  sessionId,
}: DeliverablesPanelProps) {
  const { state, deliverables, error, run } = useDocument()
  const ready = Boolean(intent && analysis && narrative && geometryArtifacts)

  const handleClick = () => {
    if (intent && analysis && narrative && geometryArtifacts) {
      void run(intent, analysis, narrative, geometryArtifacts, sessionId)
    }
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Deliverables</h2>
        <Button
          size="sm"
          disabled={!ready || state === 'running'}
          onClick={handleClick}
        >
          {state === 'running' ? 'Packaging…' : 'Generate documents'}
        </Button>
      </div>
      {error && (
        <div className="text-xs text-red-600">
          {error.message}
          {typeof error.retry_after === 'number' && (
            <span className="ml-2 text-muted-foreground">
              retry in {error.retry_after}s
            </span>
          )}
        </div>
      )}
      {deliverables && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <a href={deliverables.report_pdf_url} target="_blank" rel="noopener" className="text-xs underline">
              Report PDF
            </a>
            <a href={deliverables.drawing_pdf_url} target="_blank" rel="noopener" className="text-xs underline">
              Drawing PDF
            </a>
            <a href={deliverables.step_url} target="_blank" rel="noopener" className="text-xs underline">
              STEP
            </a>
            <a href={deliverables.glb_url} target="_blank" rel="noopener" className="text-xs underline">
              GLB
            </a>
            <a href={deliverables.svg_url} target="_blank" rel="noopener" className="text-xs underline col-span-2">
              SVG section
            </a>
          </div>
          <PdfPreview url={deliverables.report_pdf_url} title="report preview" />
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 5: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- components/deliverables/DeliverablesPanel.test.tsx
```
Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/frontend/components/deliverables/
git commit -m "feat(frontend): add DeliverablesPanel with inline PDF preview"
```

---

## Task 8: Wire panels into /design page

**Files:**
- Modify: `apps/frontend/app/design/page.tsx`

- [ ] **Step 1: Read the existing page structure**

Run: `cat apps/frontend/app/design/page.tsx`

Note three things:
- the existing import block (alphabetical, grouped)
- the `useGenerateStream()` return shape (`result` contains the cached artifacts)
- the existing JSX layout (the 3-column grid or single column container)

- [ ] **Step 2: Add imports for the three new panels**

In `apps/frontend/app/design/page.tsx`, add to the imports block:

```typescript
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { NarrativePanel } from '@/components/narrative/NarrativePanel'
import { DeliverablesPanel } from '@/components/deliverables/DeliverablesPanel'
import type { AnalysisResult, NaturalReport } from '@/lib/types'
```

- [ ] **Step 3: Add new state and a default material**

Inside `DesignPageInner` (or whatever the inner component is called), add right after the existing `useState` block:

```typescript
const [materialName, setMaterialName] = useState<string>('steel_a36')
const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
const [narrative, setNarrative] = useState<NaturalReport | null>(null)
```

`materialName` may already be threaded into FormPanel — if it is, do NOT duplicate it; reuse the existing variable. The grep below tells you:

Run: `grep -n "materialName\|material_name" apps/frontend/app/design/page.tsx`

If it returns nothing, use the new state above. If it returns existing references, only add `analysis` and `narrative` and skip `materialName`.

`setMaterialName` is here to silence the "declared but never used" lint warning until the FormPanel wires it in; if FormPanel does not currently surface material selection, leave `setMaterialName` in place (it will be used in a later task or by MaterialSelector).

- [ ] **Step 4: Compute geometryArtifacts from useGenerateStream result**

Locate the line where `useGenerateStream()` is destructured (`const { state: genState, start: startGen, result, ... } = useGenerateStream()`). Right after that block, add:

```typescript
const geometryArtifacts = result
  ? {
      mass_properties: result.mass_properties,
      step_url: result.artifacts.step_url,
      glb_url: result.artifacts.glb_url,
      svg_url: result.artifacts.svg_url,
    }
  : null
```

The `GenerateResponse` type has `artifacts` and `mass_properties` siblings, but the `/document` endpoint expects them combined inside `geometry_artifacts.mass_properties`. The block above does that reshape.

- [ ] **Step 5: Mount the three new panels in the JSX layout**

Locate the JSX that renders `ViewerPanel`. Right after it (inside the same vertical stack), insert:

```tsx
<AnalysisPanel
  intent={intent}
  materialName={materialName}
  onResult={setAnalysis}
/>
<NarrativePanel
  intent={intent}
  analysis={analysis}
  sessionId={sessionId}
  onReport={setNarrative}
/>
<DeliverablesPanel
  intent={intent}
  analysis={analysis}
  narrative={narrative}
  geometryArtifacts={geometryArtifacts}
  sessionId={sessionId}
/>
```

If the layout is a CSS grid where ViewerPanel takes the center cell, wrap the four (ViewerPanel + the three new) in `<div className="space-y-3 overflow-y-auto">…</div>` so the right and left columns stay aligned.

- [ ] **Step 6: Type check**

Run from `apps/frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors. If there are errors about `intent` type or `sessionId` type, narrow them with the exact union the page already uses (`DesignIntent | null` and `string | null`).

- [ ] **Step 7: Manual smoke (optional — only if backend running)**

If `uvicorn` is running on `:8080` and `NEXT_PUBLIC_API_URL=http://localhost:8080` is exported, run from `apps/frontend/`:
```bash
npm run dev
```
Open `http://localhost:3000/design?preset=flywheel`, complete the form, click each new button in sequence. Skip this step if backend is offline; the integration test in Task 14 covers wiring with msw.

- [ ] **Step 8: Commit**

```bash
git add apps/frontend/app/design/page.tsx
git commit -m "feat(frontend): mount AnalysisPanel, NarrativePanel, DeliverablesPanel in /design"
```

---

## Task 9: Extend msw handlers

**Files:**
- Modify: `apps/frontend/test/msw/handlers.ts`

- [ ] **Step 1: Inspect existing handler patterns**

Run: `tail -n 30 apps/frontend/test/msw/handlers.ts`

You should see the existing `http.post('*/generate', …)` handler. Mirror its style.

- [ ] **Step 2: Add /analyze, /explain, /document handlers**

Append to the `handlers` array in `apps/frontend/test/msw/handlers.ts`:

```typescript
  http.post('*/analyze', async () =>
    HttpResponse.json({
      intent_type: 'Flywheel_Rim',
      material_name: 'steel_a36',
      material_yield_mpa: 250,
      formula: 'sigma = rho*omega^2*R^2 (thin-rim centrifugal)',
      stress_max_pa: 4.84e7,
      displacement_max_m: 6.05e-5,
      safety_factor: 5.16,
      verdict: 'pass',
      inputs: { angular_velocity_rad_s: 314.16, outer_diameter_m: 0.5 },
      notes: 'thin-rim approximation; valid when thickness << outer radius',
    }),
  ),

  http.post('*/explain', () =>
    new HttpResponse(
      sseBody([
        { event: 'progress', data: { step: 'generating' } },
        { event: 'chunk', data: { text: 'The flywheel ' } },
        { event: 'chunk', data: { text: 'is well below the yield limit.' } },
        { event: 'progress', data: { step: 'parsing' } },
        {
          event: 'final',
          data: {
            report: {
              summary: 'The flywheel is well below the yield limit.',
              risks: ['Stress is comfortable.'],
              suggestions: ['Inspect bearings yearly.'],
              analogies: ['Five times stronger than needed.'],
              facts_used: ['safety_factor', 'stress_max_mpa'],
            },
            cache_hit: false,
            cache_key: 'mock-explain',
          },
        },
      ]),
      { headers: { 'Content-Type': 'text/event-stream' } },
    ),
  ),

  http.post('*/document', async () =>
    HttpResponse.json({
      report_pdf_url: 'https://example.com/report.pdf',
      drawing_pdf_url: 'https://example.com/drawing.pdf',
      step_url: 'https://mock/step',
      glb_url: '/mock.glb',
      svg_url: 'https://mock/svg',
      cache_hit: false,
      cache_key: 'mock-doc',
    }),
  ),
```

The `sseBody` helper already exists in the file (used by the `/generate` SSE handler).

- [ ] **Step 3: Run the full frontend test suite**

```bash
cd apps/frontend && npm test
```
Expected: all tests pass, no msw warnings about unhandled requests.

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/test/msw/handlers.ts
git commit -m "test(frontend): add msw handlers for /analyze, /explain, /document"
```

---

## Task 10: Integration test — full pipeline

**Files:**
- Create: `apps/frontend/test/integration/full_pipeline.test.tsx`

- [ ] **Step 1: Write the integration test**

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel'
import { NarrativePanel } from '@/components/narrative/NarrativePanel'
import { DeliverablesPanel } from '@/components/deliverables/DeliverablesPanel'
import type {
  AnalysisResult,
  CachedArtifacts,
  DesignIntent,
  NaturalReport,
} from '@/lib/types'
import { useState } from 'react'

const INTENT: DesignIntent = {
  type: 'Flywheel_Rim',
  fields: { rpm: { value: 3000, source: 'extracted' } },
  composed_of: [],
}

const ARTIFACTS: CachedArtifacts = {
  mass_properties: {
    volume_m3: 0.01, mass_kg: 75,
    center_of_mass: [0, 0, 0], bbox_m: [0, 0, 0, 1, 1, 1],
  },
  step_url: 'https://mock/step',
  glb_url: '/mock.glb',
  svg_url: 'https://mock/svg',
}

function Harness() {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [narrative, setNarrative] = useState<NaturalReport | null>(null)
  return (
    <div>
      <AnalysisPanel intent={INTENT} materialName="steel_a36" onResult={setAnalysis} />
      <NarrativePanel
        intent={INTENT}
        analysis={analysis}
        sessionId="sid"
        onReport={setNarrative}
      />
      <DeliverablesPanel
        intent={INTENT}
        analysis={analysis}
        narrative={narrative}
        geometryArtifacts={ARTIFACTS}
        sessionId="sid"
      />
    </div>
  )
}

describe('full pipeline integration (panels stacked, msw default handlers)', () => {
  it('cascades intent → analysis → narrative → deliverables', async () => {
    render(<Harness />)

    // 1. Analyze
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => expect(screen.getByText('PASS')).toBeInTheDocument())

    // 2. Explain — now enabled because analysis state set
    const explainBtn = await screen.findByRole('button', { name: /^explain$/i })
    expect(explainBtn).toBeEnabled()
    await userEvent.click(explainBtn)
    await waitFor(() =>
      expect(
        screen.getByText('The flywheel is well below the yield limit.'),
      ).toBeInTheDocument(),
    )

    // 3. Generate documents — now enabled because narrative state set
    const docBtn = await screen.findByRole('button', { name: /generate documents/i })
    await waitFor(() => expect(docBtn).toBeEnabled())
    await userEvent.click(docBtn)
    await waitFor(() => expect(screen.getByText('Report PDF')).toBeInTheDocument())
    expect(screen.getByTitle(/report preview/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run, confirm PASS**

```bash
cd apps/frontend && npm test -- test/integration/full_pipeline.test.tsx
```
Expected: 1 test passes.

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/test/integration/full_pipeline.test.tsx
git commit -m "test(frontend): add full pipeline integration test (analyze → explain → document)"
```

---

## Task 11: Backend CORS regex update

**Files:**
- Modify: `apps/backend/services/interpreter/app.py`

- [ ] **Step 1: Inspect existing CORSMiddleware setup**

Run: `grep -nA 8 "CORSMiddleware" apps/backend/services/interpreter/app.py`

Find the `app.add_middleware(CORSMiddleware, …)` call.

- [ ] **Step 2: Add allow_origin_regex parameter**

Edit `apps/backend/services/interpreter/app.py`. Locate the existing `app.add_middleware(CORSMiddleware, …)` call and add the `allow_origin_regex` argument. For example, if the existing block is:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

change it to:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origin_regex` is an OR with `allow_origins`: an origin matches if it appears in either list.

- [ ] **Step 3: Verify ruff + mypy clean**

```bash
cd apps/backend
uv run ruff check services/interpreter/app.py
uv run mypy services/interpreter/app.py
```
Expected: both clean.

- [ ] **Step 4: Sanity test**

```bash
cd apps/backend
uv run python -c "
from fastapi.testclient import TestClient
from services.interpreter.app import create_app
from pathlib import Path
# Build a minimal app using the actual factory; the import alone proves the
# middleware regex did not break the create_app signature.
print('app import OK')
"
```
Expected: `app import OK`.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/app.py
git commit -m "feat(backend): allow Vercel domains via allow_origin_regex"
```

---

## Task 12: Backend Dockerfile + .dockerignore

**Files:**
- Create: `apps/backend/Dockerfile`
- Create: `apps/backend/.dockerignore`

- [ ] **Step 1: Write `apps/backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

# Build dependencies for build123d (OpenCASCADE runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*

# uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first (better layer caching). The pyproject is enough; uv.lock
# is optional and improves reproducibility when present.
COPY apps/backend/pyproject.toml apps/backend/uv.lock* /app/
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Copy the rest of the backend
COPY apps/backend /app

ENV PYTHONPATH=/app PORT=8080
EXPOSE 8080

CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT}
```

- [ ] **Step 2: Write `apps/backend/.dockerignore`**

```
.venv
.pytest_cache
.ruff_cache
.mypy_cache
__pycache__
*.pyc
tests/
.env*
*.md
.gitignore
data/demo_artifacts/*
```

- [ ] **Step 3: Local build sanity (optional — requires Docker installed)**

Run from repo root:
```bash
docker build -t mechdesign-backend-test -f apps/backend/Dockerfile .
docker run --rm -p 8081:8080 -e GCP_PROJECT_ID=mechdesign-ai -e GCP_REGION=us-central1 \
  -e VERTEX_AI_ENDPOINT=gemini-2.5-flash -e GCS_BUCKET_ARTIFACTS=mechdesign-ai-artifacts \
  mechdesign-backend-test &
sleep 5
curl -fsS http://127.0.0.1:8081/healthz
docker stop $(docker ps -q --filter ancestor=mechdesign-backend-test)
```
Expected: `{"status":"ok"}`.

Skip this step if Docker is not installed; Cloud Build (in Task 13) builds the same image remotely.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/Dockerfile apps/backend/.dockerignore
git commit -m "build(backend): add Dockerfile and .dockerignore for Cloud Run deploy"
```

---

## Task 13: Cloud Run deploy script + runtime SA

**Files:**
- Modify: `infra/deploy-backend.sh` (existing — replace contents)

- [ ] **Step 1: Inspect what is in the existing script**

Run: `cat infra/deploy-backend.sh`

If the file already contains a partial deploy, replace it. If it does not exist or is just a placeholder, write the new contents directly.

- [ ] **Step 2: Replace the script** — `infra/deploy-backend.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="${PROJECT:-mechdesign-ai}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-mechdesign-backend}"
BUCKET="${BUCKET:-mechdesign-ai-artifacts}"
SA_NAME="${SA_NAME:-mechdesign-runtime}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
REPO="${REPO:-backend}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

echo "==> Project: ${PROJECT}, Region: ${REGION}, Service: ${SERVICE}"

# 1. Enable required APIs (idempotent)
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  --project="${PROJECT}"

# 2. Create Artifact Registry repo (idempotent)
gcloud artifacts repositories describe "${REPO}" \
  --project="${PROJECT}" --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${REPO}" \
       --project="${PROJECT}" --location="${REGION}" --repository-format=docker

# 3. Create runtime SA + grant roles (idempotent)
gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT}" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "${SA_NAME}" \
       --project="${PROJECT}" --display-name="Cloud Run runtime for ${SERVICE}"

for role in \
    roles/storage.objectAdmin \
    roles/aiplatform.user \
    roles/datastore.user \
    roles/serviceusage.serviceUsageConsumer
do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" --condition=None >/dev/null
done

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="${PROJECT}" >/dev/null

# 4. Build image via Cloud Build (no local Docker required)
gcloud builds submit \
  --project="${PROJECT}" \
  --tag="${IMAGE}" \
  --file=apps/backend/Dockerfile \
  .

# 5. Deploy
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${SA_EMAIL}" \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=120 \
  --concurrency=20 \
  --max-instances=5 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCP_REGION=${REGION},VERTEX_AI_ENDPOINT=gemini-2.5-flash,GEMMA_TEMPERATURE=0.2,GEMMA_MAX_TOKENS=2048,GEMMA_TIMEOUT_SECONDS=60,GCS_BUCKET_ARTIFACTS=${BUCKET},SIGNED_URL_TTL_HOURS=24,SESSION_TTL_HOURS=24,SESSION_MAX_RETRIES=5,RATE_LIMIT_PER_MINUTE=30,DEGRADED_MODE_FAILURE_THRESHOLD=2,DEGRADED_MODE_DURATION_SECONDS=60,CORS_ALLOWED_ORIGINS=http://localhost:3000"

URL=$(gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" --region="${REGION}" --format='value(status.url)')

echo "==> Deployed: ${URL}"
echo "==> Set NEXT_PUBLIC_API_URL=${URL} in Vercel (Production scope)"
```

- [ ] **Step 3: Make it executable and run**

Run from repo root:
```bash
chmod +x infra/deploy-backend.sh
./infra/deploy-backend.sh
```

The script will:
1. Enable APIs (no-op if already enabled).
2. Create Artifact Registry repo `backend` in `us-central1` (no-op if exists).
3. Create `mechdesign-runtime@` SA and grant 5 roles (no-op for each binding that exists).
4. Build the Docker image via Cloud Build (~3-5 min).
5. Deploy to Cloud Run (~1-2 min).

Expected final output: `==> Deployed: https://mechdesign-backend-<hash>-uc.a.run.app`. Copy that URL; it goes into Vercel in Task 14.

- [ ] **Step 4: Verify the deploy**

```bash
URL=$(gcloud run services describe mechdesign-backend --project=mechdesign-ai --region=us-central1 --format='value(status.url)')
curl -fsS "$URL/healthz"
```
Expected: `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add infra/deploy-backend.sh
git commit -m "build(infra): Cloud Run deploy script with runtime SA + Artifact Registry"
```

---

## Task 14: Vercel env config + GCS CORS update

**Files:**
- Manual: Vercel dashboard
- Bash: GCS bucket CORS

- [ ] **Step 1: Set `NEXT_PUBLIC_API_URL` in Vercel**

Manual step (no code change). In Vercel dashboard → Settings → Environment Variables:

| Name | Value | Environment |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | the URL printed by Task 13 (e.g. `https://mechdesign-backend-abc123-uc.a.run.app`) | Production |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8080` | Development (optional — only useful if running `vercel dev`) |

After saving, redeploy the frontend on Vercel (Deployments → Latest → Redeploy) so the new env var is baked into the static bundle.

- [ ] **Step 2: Identify the Vercel production domain**

From the Vercel dashboard (Project → Domains) or the deploy output, copy the production domain (e.g. `mechdesign.vercel.app`).

- [ ] **Step 3: Update the GCS bucket CORS allowlist**

Run from repo root:
```bash
DOMAIN="https://mechdesign.vercel.app"  # adjust to your actual domain
cat > /tmp/cors.json <<EOF
[{
  "origin": ["${DOMAIN}", "http://localhost:3000"],
  "method": ["GET","HEAD","OPTIONS"],
  "responseHeader": ["Content-Type","Range"],
  "maxAgeSeconds": 3600
}]
EOF
gcloud storage buckets update gs://mechdesign-ai-artifacts --cors-file=/tmp/cors.json
gcloud storage buckets describe gs://mechdesign-ai-artifacts --format="json(cors_config)"
```

Expected: CORS config with the two origins.

- [ ] **Step 4: Sanity test — fetch a signed URL from Vercel**

Open the production Vercel site (`https://<your-domain>.vercel.app/design?preset=flywheel`), open DevTools → Network, click through the pipeline. Verify:
- `OPTIONS /analyze` returns `200` with `Access-Control-Allow-Origin: https://<your-domain>.vercel.app`
- `POST /analyze` returns `200` JSON
- GCS signed URLs (in the document panel) load in iframe without CORS errors

If iframe shows blank with no console error, the PDF preview probably works but the iframe lazy-loaded — wait a moment.

- [ ] **Step 5: No commit needed unless `infra/cors.json` is checked in**

If you want to version-control the CORS config, save it under `infra/gcs-cors.json` and commit:
```bash
cp /tmp/cors.json infra/gcs-cors.json
git add infra/gcs-cors.json
git commit -m "build(infra): document GCS bucket CORS for Vercel + localhost"
```

---

## Task 15: Playwright E2E smoke

**Files:**
- Create: `apps/frontend/e2e/full_pipeline.spec.ts`

- [ ] **Step 1: Inspect existing Playwright config**

Run: `cat apps/frontend/playwright.config.ts`

Note the base URL and the test directory pattern. Existing E2E tests live in `apps/frontend/e2e/`.

- [ ] **Step 2: Write the spec** — `apps/frontend/e2e/full_pipeline.spec.ts`

```typescript
import { expect, test } from '@playwright/test'

test.describe('full pipeline', () => {
  test('preset flywheel completes analyze, explain, document', async ({ page }) => {
    // Pre-seed any required env (frontend should already have NEXT_PUBLIC_API_URL).
    await page.goto('/design?preset=flywheel')

    // Wait for the form to render with the preset prompt populated.
    const prompt = page.locator('textarea')
    await expect(prompt).toBeVisible()

    // The integration test in Task 10 covers the full hook wiring with msw.
    // This E2E walks the user flow against the LIVE backend (or msw if
    // Playwright is configured with a service worker — current config uses
    // live backend).

    // Click Send (interpret)
    await page.getByRole('button', { name: /send/i }).click()

    // After the SSE finishes, the form should show some tri-state markers.
    // (We allow up to 15s for cold Cloud Run.)
    await page.waitForTimeout(2000)

    // Fill any clearly missing dimension fields if visible (best-effort).
    const outerInput = page.locator('input[name="outer_diameter_m"]')
    if (await outerInput.count()) await outerInput.fill('0.5')
    const innerInput = page.locator('input[name="inner_diameter_m"]')
    if (await innerInput.count()) await innerInput.fill('0.1')
    const thickInput = page.locator('input[name="thickness_m"]')
    if (await thickInput.count()) await thickInput.fill('0.05')

    // Click Generate
    await page.getByRole('button', { name: /^generate$/i }).click()
    await page.waitForSelector('canvas', { timeout: 30_000 })

    // Click Analyze
    await page.getByRole('button', { name: /^analyze$/i }).click()
    await expect(page.locator('text=/PASS|WARN|FAIL/')).toBeVisible({ timeout: 15_000 })

    // Click Explain
    await page.getByRole('button', { name: /^explain$/i }).click()
    await expect(page.locator('text=Facts cited:')).toBeVisible({ timeout: 30_000 })

    // Click Generate documents
    await page.getByRole('button', { name: /generate documents/i }).click()
    await expect(page.locator('iframe[title="report preview"]')).toBeVisible({ timeout: 30_000 })
  })
})
```

- [ ] **Step 3: Run the spec against localhost (manual smoke)**

In one terminal:
```bash
cd apps/backend
unset GCP_PROJECT_ID GCP_REGION GCS_BUCKET_ARTIFACTS CORS_ALLOWED_ORIGINS
export GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/mechdesign-ai/gcs-signer-key.json
export VERTEX_AI_ENDPOINT=gemini-2.5-flash
export GEMMA_TIMEOUT_SECONDS=60
uv run uvicorn main:app --host 127.0.0.1 --port 8080
```

In a second terminal:
```bash
cd apps/frontend
NEXT_PUBLIC_API_URL=http://localhost:8080 npm run dev
```

In a third terminal:
```bash
cd apps/frontend
npx playwright test e2e/full_pipeline.spec.ts
```

Expected: 1 test passes (~30-40 s total).

If a step times out (e.g. `canvas` not appearing), inspect the running browser via `npx playwright test --headed`.

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/e2e/full_pipeline.spec.ts
git commit -m "test(frontend): add Playwright E2E for full pipeline"
```

---

## Task 16: README update + final gate

**Files:**
- Modify: `apps/frontend/README.md`

- [ ] **Step 1: Inspect existing README**

Run: `cat apps/frontend/README.md`

- [ ] **Step 2: Add a "Backend endpoints used" section**

Append at the end of `apps/frontend/README.md`:

```markdown
## Backend endpoints consumed

This frontend talks to a FastAPI backend (`apps/backend/`) via `NEXT_PUBLIC_API_URL`.

| Endpoint | Method | Hook | Purpose |
|---|---|---|---|
| `/interpret` | POST (SSE) | `useInterpretStream` | NL prompt → `DesignIntent` |
| `/generate` | POST (SSE) | `useGenerateStream` | `DesignIntent` → STEP/GLB/SVG + mass |
| `/analyze` | POST (JSON) | `useAnalyze` | `DesignIntent` → `AnalysisResult` (SF, verdict, formula) |
| `/explain` | POST (SSE) | `useExplainStream` | `AnalysisResult` → streamed `NaturalReport` |
| `/document` | POST (JSON) | `useDocument` | full pipeline → `Deliverables` (PDFs + URLs) |

### Environment

- Local dev: backend on `http://localhost:8080`; set `NEXT_PUBLIC_API_URL=http://localhost:8080`.
- Production: backend on Cloud Run (`mechdesign-backend` service, `mechdesign-ai` project). Set `NEXT_PUBLIC_API_URL` in Vercel project settings to the Cloud Run URL.

### Pipeline UI

`/design` page mounts six panels:
- `FormPanel` — tri-state form filled by `/interpret`
- `ChatPanel` — conversation history
- `ViewerPanel` — R3F 3D model from GLB
- `AnalysisPanel` — verdict badge, SF, formula
- `NarrativePanel` — streaming `NaturalReport`
- `DeliverablesPanel` — 5 download links + inline PDF preview
```

- [ ] **Step 3: Run the full test suite as the final gate**

```bash
cd apps/frontend
npm test
npx tsc --noEmit
```

Expected:
- All vitest tests pass (existing + new from Tasks 1-10).
- TypeScript clean.

If anything fails, fix before committing. Common issue: a hook import path uses `@/lib/hooks/foo` instead of relative `../foo` — adjust per the repo's tsconfig `paths` setting (the prefix `@/` should already work).

- [ ] **Step 4: Commit**

```bash
git add apps/frontend/README.md
git commit -m "docs(frontend): document new endpoints, hooks, and Vercel env var"
```

- [ ] **Step 5: Update root `CLAUDE.md` with frontend status**

Once all tasks pass, append to `CLAUDE.md`'s "Implementation status" the new state of the frontend:

The existing bullet is:
```markdown
- **Frontend** — `apps/frontend/` with viewer, locale toggle, `useGenerateStream`/`useArtifacts` hooks, `/design` route
```

Replace it with:
```markdown
- **Frontend** — `apps/frontend/` with `/design` page wired end-to-end through the pipeline (FormPanel + ViewerPanel + AnalysisPanel + NarrativePanel + DeliverablesPanel). Hooks: `useInterpretStream`, `useGenerateStream`, `useAnalyze`, `useExplainStream`, `useDocument`. Production deploys to Vercel; `NEXT_PUBLIC_API_URL` points at Cloud Run `mechdesign-backend`.
```

Commit:
```bash
git add CLAUDE.md
git commit -m "docs(claude): mark frontend wiring + Cloud Run deploy live"
```

---

## Done criteria

All of the following hold:

- [ ] Tasks 1-16 commits land in order, each green at commit time
- [ ] `npm test` in `apps/frontend/` exits 0
- [ ] `npx tsc --noEmit` in `apps/frontend/` exits 0
- [ ] `npx playwright test e2e/full_pipeline.spec.ts` exits 0 against localhost backend
- [ ] Cloud Run service `mechdesign-backend` reachable at its URL
- [ ] `NEXT_PUBLIC_API_URL` set in Vercel and the Vercel preview/prod talks to Cloud Run
- [ ] GCS bucket CORS allows the Vercel domain
- [ ] `/design` page renders 6 panels and the demo script in §9 of the spec works end-to-end

## Out of scope for this plan

- S1 multi-turn agent loop refactor (separate plan)
- Mobile-first responsive (best-effort responsive only)
- Auth / sign-in
- Analytics
- Vercel preview environment hooked to a specific Cloud Run revision via `--tag`

## Notes for the executor

- DO NOT use `--no-verify` on commits.
- DO NOT add `Co-Authored-By` lines.
- ASCII-only in code strings. The frontend is TypeScript so `σ` etc. are fine in JSX text content but avoid in identifiers.
- If `npm test` reports an unhandled msw request, add the missing handler to `test/msw/handlers.ts` BEFORE committing the test.
- If Cloud Build fails on `uv sync --frozen --no-dev` because no `uv.lock` is checked in, the `|| uv sync --no-dev` fallback in the Dockerfile handles it.
- If the runtime SA's roles list shows a `concurrent policy changes` error during `add-iam-policy-binding`, `sleep 2 && retry` — gcloud's optimistic concurrency on IAM bindings flaps under quick repeats.
- The `useState<AnalysisResult | null>` patterns in `/design/page.tsx` and tests use the exact type names from `lib/types.ts`; do not invent variant names.
- If a step's expected output does not match, STOP and report — do not muddle through.
