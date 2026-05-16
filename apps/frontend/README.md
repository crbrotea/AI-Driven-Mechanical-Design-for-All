# AI-Driven Mechanical Design — Frontend

Next.js 14 frontend for the AI-Driven Mechanical Design platform.

Consumes S1 (Interpreter) + S2 (Geometry) backend APIs.

## Local development

```bash
cd apps/frontend
pnpm install
cp .env.local.example .env.local
# Edit NEXT_PUBLIC_API_URL to your backend URL
pnpm dev
```

Open http://localhost:3000.

## Testing

```bash
pnpm test              # unit + component + integration (Vitest + MSW)
pnpm test:watch        # watch mode
pnpm lint              # ESLint
pnpm type-check        # tsc --noEmit
```

## Build

```bash
pnpm build
pnpm start             # production server on :3000
```

## Deploy to Vercel

1. Push repo to GitHub
2. Import into Vercel
3. Set `NEXT_PUBLIC_API_URL` environment variable
4. Deploy — every push to main auto-deploys; PRs get preview URLs

## Architecture

- **Routes**: `/` (SSG landing) + `/design` (client-side app)
- **State**: SWR (server) + Zustand (UI, persisted to localStorage)
- **Streams**: direct browser → Cloud Run (no Next.js proxy)
- **i18n**: next-intl with ES + EN toggle
- **3D**: React Three Fiber + drei with PBR studio environment
- **Forms**: React Hook Form + Zod, tri-state rendering (extracted/defaulted/missing/user/invalid)

See [design spec](../../docs/superpowers/specs/2026-04-19-frontend-design.md).

## Runbook: backend down

The `ErrorBanner` renders with `gcs_unavailable` or `connection_lost` codes.
Degraded mode is driven by the backend's demo-fallback endpoint; frontend is transparent.

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
