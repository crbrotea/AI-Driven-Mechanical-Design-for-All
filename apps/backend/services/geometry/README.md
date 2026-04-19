# S2 Geometry

Converts `DesignIntent` (from S1) into professional CAD artifacts via build123d.

See the [design spec](../../../docs/superpowers/specs/2026-04-19-s2-geometry-design.md) for context.

## Endpoints

- `POST /generate` — SSE stream. Body: `{ intent, session_id?, material_name? }`
- `GET /generate/artifacts/{intent_hash}` — re-hydrate cached artifacts

## Primitives

Seven registered primitives cover the three hero demos:
- `Flywheel_Rim`, `Shaft`, `Bearing_Housing` (hero 1)
- `Pelton_Runner`, `Housing`, `Mounting_Frame` (hero 2)
- `Hinge_Panel` (hero 3 — `Tensor_Rod` and `Base_Connector` are referenced
  in composition rules but not yet implemented as builders)

Each primitive is a pure function under `services/geometry/primitives/`
with a uniform contract: SI inputs, `build123d.Part` output.

## Composition

The registry at `services/geometry/composition_rules.py` maps
`(main, composed)` pairs to parameter-derivation functions. Seven rules
cover all hero-demo compositions. Missing pairs raise
`GeometryError(COMPOSITION_RULE_MISSING)`.

## Local development

```bash
cd apps/backend
uv run pytest -m "not vertex" -v   # unit + component
uv run pytest -m integration -v    # hero demo integration tests
```

## Running the service

The S2 router attaches to the same FastAPI app as S1. Run via:

```bash
cd apps/backend
uv run uvicorn main:app --reload --port 8080
```

Then:
```bash
curl -N -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"intent":{"type":"Shaft","fields":{"diameter_m":{"value":0.05,"source":"extracted"},"length_m":{"value":0.5,"source":"extracted"}},"composed_of":[]},"material_name":"steel_a36"}'
```

## Runbook: GCS is down

The `DegradedModeBreaker` at `app.state.geometry_cache_breaker` opens
after 2 consecutive GCS failures and stays open for 60 seconds.
While open, `/generate` requests return a `gcs_unavailable` SSE error.

For the live demo, pre-generated hero-demo artifacts under
`apps/backend/data/demo_artifacts/{intent_hash}/` provide a local
fallback (see `fallback.py`). Populate this directory in CI before the
final submission.

## Cost controls

- `tessellation=1mm` keeps GLB files ~100KB–2MB
- 24h signed URL TTL matches session TTL
- Rate limit **10 req/min per IP** (enforced at Cloud Armor)
- Cache global by intent-value hash → hero demos cost ~$0 after first
  generation

## Testing strategy

Tests verify geometric INVARIANTS (volume, bbox, determinism), not
exact BREP equality. See `docs/superpowers/specs/2026-04-19-s2-geometry-design.md`
§7 for the full pyramid.
