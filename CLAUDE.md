# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project State

**Hackathon submission** — "Gemma 4 Good", deadline **2026-05-18 18:00**. Scoring weights: 40 Impact/Vision + 30 Storytelling + 30 Technical Depth.

The repo is currently **plan-stage**: no source code has been committed yet. Only design documents exist:
- `DESIGN.md` — system-wide architecture, infra, roadmap, deliverables
- `docs/superpowers/specs/` — per-subsystem design specs (S1 interpreter approved)

Before adding code, read `DESIGN.md` for the big picture and any matching spec in `docs/superpowers/specs/` for the subsystem being implemented.

## Core Mental Model: 5 Subsystems

The platform turns natural-language prompts into physically-validated mechanical blueprints via a pipeline of 5 small, independent services (Hexagonal / Ports & Adapters):

| Subsystem | Role | Key tech |
|---|---|---|
| **S1 Interpreter** | NL → structured `DesignIntent` | Gemma 4 + function calling (Vertex AI) |
| **S2 Geometry** | `DesignIntent` → parametric 3D | build123d + primitives library |
| **S3 Physics** | Structural/dynamic analysis | CalculiX + gmsh + analytical fallback |
| **S4 Explainer** | Numerical results → NL report | Gemma 4 (grounded, temp 0.3) |
| **S5 Documenter** | Export STEP / GLB / SVG / PDF | build123d export + reportlab |

**Non-negotiable principle**: every subsystem MUST be replaceable without affecting the others. Input/output contracts go in `packages/contracts/` as JSON Schemas (Pydantic on backend → typed into Zod/TS on frontend).

**Golden rule from the design**: every component has a DOCUMENTED fallback. FEA falls back to analytical formulas; Gemma falls back to "manual mode" UI with no LLM.

## Key Design Decisions (don't re-litigate without cause)

These were deliberately chosen in the design specs. If you think one is wrong, explain WHY with evidence before proposing alternatives.

- **Materials storage**: local `apps/backend/data/materials.json` (~50-100 curated entries), NOT BigQuery. The tool interface (`search_materials`, `get_material_properties`) is what matters; the backing store is a swap-later detail.
- **S1 conversation model**: hybrid "extract → form" — LLM extracts what it can, frontend shows pre-filled form with tri-state field markers (`extracted` / `defaulted` / `missing` / `invalid`). LLM confidence scores are NOT used (poorly calibrated).
- **S1 `/refine` endpoint never calls Gemma** — deterministic merge + re-validate only. Target <100ms.
- **Units**: accept imperial + metric, normalize to SI internally via `pint`. Preserve user's original string for display.
- **Language**: bilingual ES + EN for user-facing text; internal schemas remain English.
- **FEA execution**: async via Cloud Tasks → Cloud Run Job (15 min timeout). Precompute hero-demo results to avoid live-demo latency.
- **S1 streaming**: SSE with `tool_call` events surfaced as chat messages — materializes agentic work for the video narrative.
- **Prompts live in `prompts/*.md`**, NOT hardcoded in Python.

## Planned Repo Layout (monorepo, see DESIGN.md §8 for full tree)

```
apps/frontend/         Next.js 14 on Vercel — App Router, R3F viewer, Vercel AI SDK
apps/backend/          FastAPI on Cloud Run — services/{interpreter,geometry,physics,explainer,documenter}
packages/contracts/    Shared JSON Schemas (source of truth)
infra/                 gcloud deploy scripts (setup.sh, deploy-backend.sh)
demos/                 Pre-computed hero demo artifacts (flywheel, hydro_generator, foldable_shelter)
```

## Stack

**Backend**: Python 3.11+, FastAPI 0.115+, `uv` for packaging, Pydantic v2, build123d (NOT CadQuery — build123d has native GLB export), CalculiX + gmsh, google-cloud-aiplatform, google-cloud-tasks, google-cloud-storage, pytest + `httpx.AsyncClient`.

**Frontend**: Next.js 14 App Router, TypeScript strict, React Three Fiber + drei, Tailwind + shadcn/ui, Zustand, Vercel AI SDK (SSE `useChat`), React Hook Form + Zod.

**Deploy**: frontend auto-deploys via Vercel GitHub App on push to `apps/frontend/`. Backend deploys via Cloud Build on push to `apps/backend/`. CORS must allow `https://*.vercel.app` + prod domain + `localhost:3000`.

## Hero Demos (the work is judged on these)

Prioritization is deliberate — do NOT add a 4th demo:
1. **Flywheel** — ROBUST. Low risk, high technical wow. Must validate σ=ρω²r²/2 within <5% error vs analytical.
2. **Hydroelectric generator** — FUNCTIONAL. Maximum Global Resilience track impact.
3. **Foldable shelter** — NARRATIVE. Visual/social impact; may have simpler physics.

Every week has a Friday Go/No-Go gate (see DESIGN.md §6). If a gate fails, cut scope — do NOT extend the week.

## Commands

No build/test tooling has been configured yet. When scaffolding `apps/backend/`, use `uv` (10-100× faster than pip) and FastAPI's conventional layout. When scaffolding `apps/frontend/`, use `create-next-app` with App Router + TypeScript strict. Update this section once `pyproject.toml` and `package.json` exist.

## Specs Workflow

This repo uses Spec-Driven Development. Per-subsystem design specs live in `docs/superpowers/specs/YYYY-MM-DD-<topic>.md` and are the authoritative source for implementation. Before touching a subsystem, read its spec. If the spec and code conflict, the spec wins until explicitly revised.

The S1 Interpreter spec (`docs/superpowers/specs/2026-04-18-s1-interpreter-design.md`) is the template for subsequent subsystem specs — sections 1-11 structure.
