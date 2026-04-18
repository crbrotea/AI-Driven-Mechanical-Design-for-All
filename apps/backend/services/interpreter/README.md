# S1 Interpreter

Converts natural-language mechanical design requests (ES/EN) into a validated `DesignIntent` via Gemma 4 agentic function calling.

See the [design spec](../../../docs/superpowers/specs/2026-04-18-s1-interpreter-design.md) for context.

## Endpoints

- `POST /interpret` — SSE stream. Body: `{ prompt, session_id? }`.
- `POST /interpret/refine` — deterministic. Body: `{ session_id, field_updates }`.
- `GET /interpret/sessions/{session_id}` — state inspection.
- `GET /healthz` — liveness probe.

## Local development

```bash
cd apps/backend
uv sync --extra dev

# Unit + component tests (fast, no GCP needed)
uv run pytest -m "not vertex" -v

# Integration tests (requires GCP credentials)
export GCP_PROJECT_ID=your-project
export GCP_REGION=us-central1
uv run pytest -m vertex -v
```

## Running the service locally

```bash
export GCP_PROJECT_ID=your-project
export GCP_REGION=us-central1
export VERTEX_AI_ENDPOINT=gemma-4-instruct
export GCS_BUCKET_ARTIFACTS=your-bucket
export CORS_ALLOWED_ORIGINS="http://localhost:3000"

uv run uvicorn main:app --reload --port 8080
```

## Example curl

```bash
curl -N -X POST http://localhost:8080/interpret \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Diseña un volante de inercia para 500 kJ a 3000 RPM"}'
```

## Architecture

Three layers:
1. **Input** — FastAPI endpoint + Firestore session loader.
2. **Agentic Orchestration** — Gemma 4 with 4 tools (`list_primitives`, `get_primitive_schema`, `search_materials`, `get_material_properties`).
3. **Validation & Output** — Pydantic-based physical range validation + tri-state DesignIntent builder.

## Runbook: "Vertex is down"

Symptoms: `/interpret` returns SSE `error` events with code `vertex_ai_timeout` or `vertex_ai_rate_limit` repeatedly.

The circuit breaker opens automatically after 2 consecutive failures and stays open for 60 seconds. During that window, all `/interpret` requests fail fast with a banner asking the user to switch to manual mode (frontend shows an empty form with primitives listed).

If the outage exceeds 5 minutes, notify the team on-call and consider manually extending the breaker duration via env var `DEGRADED_MODE_DURATION_SECONDS`.

## Cost controls

- `temperature=0.2`, `max_output_tokens=2048` keeps per-request cost < $0.01.
- Rate limit: 30 req/min per IP — enforced at infra level via Cloud Armor policy (see `infra/setup.sh`), not in-app.
- Session TTL 24h (Firestore TTL policy must be enabled on `interpreter_sessions`).
- Prompt hashes (not plaintext) are logged for PII safety.

## Golden fixtures

Golden fixture capture is manual for the hackathon: once integration tests pass against real Vertex AI (Task 20), snapshot the actual responses into `tests/fixtures/gemma_responses/*.json` and reference them from component tests. This enables fast iteration on downstream logic without burning Vertex quota.
