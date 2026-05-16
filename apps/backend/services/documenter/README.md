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
