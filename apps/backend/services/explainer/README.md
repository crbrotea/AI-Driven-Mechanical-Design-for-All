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
- `gemma_timeout` if Vertex times out before the first chunk
- `gemma_rate_limited` (HTTP 429) on quota exhausted
- `gemma_failed` (HTTP 502) on any other Vertex error

The client retries with the suggested `retry_after`. No server-side retry on
Vertex failures. JSON parse failures are retried once with a stricter prompt.

## Out of scope (deferred)

- Bilingual ES + EN -- English only for MVP
- GCS-persisted cache -- only in-memory
- Pre-baked hero report files -- optional stretch goal
- Multi-turn refinement -- separate plan
