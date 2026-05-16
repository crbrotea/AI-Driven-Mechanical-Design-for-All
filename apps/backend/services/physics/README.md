# S3 Physics

Sync analytical structural analysis. Maps a `DesignIntent` (from S1) to an
`AnalysisResult` (stress, displacement, safety factor, verdict).

See the [design spec](../../../../docs/superpowers/specs/2026-05-16-s3-physics-design.md)
for context and rationale.

## Endpoint

- `POST /analyze` — sync JSON. Body: `{ intent: DesignIntent, material_name?: string }`

```bash
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "type": "Flywheel_Rim",
      "fields": {
        "outer_diameter_m": {"value": 0.5, "source": "extracted"},
        "inner_diameter_m": {"value": 0.1, "source": "extracted"},
        "thickness_m": {"value": 0.05, "source": "extracted"},
        "rpm": {"value": 3000, "source": "extracted"}
      },
      "composed_of": []
    },
    "material_name": "steel_a36"
  }'
```

## Solvers

| `intent.type` | Solver | Closed-form formula |
|---|---|---|
| `Flywheel_Rim` | `solvers/flywheel.py` | sigma = rho*omega^2*R^2 (thin-rim centrifugal) |
| `Pelton_Runner` | `solvers/hydro.py` | tau = 16T/(pi*d^3), T = P_hyd/omega |
| `Hinge_Panel` | `solvers/shelter.py` | sigma = 6PL^2/t^2 (cantilever wind bending) |

Each solver is a pure function with the same contract:
`(geometry, load_case, material) -> AnalysisResult`.

## Local development

```bash
cd apps/backend
uv run pytest tests/unit/physics tests/component/physics -v
uv run pytest tests/integration/physics -m integration -v
```

## Verdict thresholds

- `PASS` — safety_factor >= 2.0
- `WARN` — 1.5 <= safety_factor < 2.0
- `FAIL` — safety_factor < 1.5

## Out of scope (deferred to S3.v2)

- CalculiX / gmsh FEA
- Cloud Tasks async execution
- Composed-primitive analysis (composed parts are absorbed by the main solver)
- Fatigue / buckling / non-linear materials / thermal derating
