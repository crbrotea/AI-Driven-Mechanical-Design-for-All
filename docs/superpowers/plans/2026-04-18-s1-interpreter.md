# S1 Interpreter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the S1 Interpreter backend subsystem — a FastAPI service that converts natural-language mechanical design requests (ES/EN) into a structured `DesignIntent` via Gemma 4 agentic function calling, with SSE streaming and tri-state field extraction.

**Architecture:** Three-layer hexagonal — Input (FastAPI + Firestore session) → Agentic Orchestration (Gemma 4 + 4 tools + unit normalizer) → Validation & Output (Pydantic + DesignIntent builder). LLM output never touches the final schema directly; a deterministic builder transforms intermediate JSON. Materials stored locally in `data/materials.json`; primitives registered as Python code.

**Tech Stack:** Python 3.11+, FastAPI 0.115+, Pydantic v2, `uv` (package mgmt), `pint` (units), `google-cloud-aiplatform` (Vertex AI / Gemma 4), `google-cloud-firestore`, `pytest`, `httpx.AsyncClient`, `uvicorn`. Structured logging via `structlog`. Deployed on Cloud Run.

**Out of scope:** Frontend (Next.js) — separate plan. S2/S3/S4/S5 subsystems — separate plans. CI/CD pipelines — covered in infra plan.

---

## Task 1: Backend project scaffolding

**Files:**
- Create: `apps/backend/pyproject.toml`
- Create: `apps/backend/services/interpreter/__init__.py`
- Create: `apps/backend/tests/__init__.py`
- Create: `apps/backend/tests/conftest.py`
- Create: `apps/backend/.python-version`

- [ ] **Step 1: Create Python version pin**

Create `apps/backend/.python-version`:
```
3.11
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `apps/backend/pyproject.toml`:
```toml
[project]
name = "mechdesign-backend"
version = "0.1.0"
description = "AI-Driven Mechanical Design — backend services"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "google-cloud-aiplatform>=1.70.0",
    "google-cloud-firestore>=2.19.0",
    "pint>=0.24.0",
    "structlog>=24.4.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.7.0",
    "mypy>=1.13.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "vertex: tests that call the real Vertex AI API (slow, costs quota)",
    "integration: integration tests requiring GCP credentials",
]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.11"
```

- [ ] **Step 3: Create package markers**

Create `apps/backend/services/interpreter/__init__.py`:
```python
"""S1 Interpreter — NL → DesignIntent via Gemma 4 agentic function calling."""
__version__ = "0.1.0"
```

Create `apps/backend/tests/__init__.py` (empty file).

- [ ] **Step 4: Create pytest conftest**

Create `apps/backend/tests/conftest.py`:
```python
"""Shared pytest fixtures."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to tests/fixtures/."""
    return FIXTURES_DIR
```

- [ ] **Step 5: Verify structure and install**

Run: `cd apps/backend && uv sync --extra dev`
Expected: `Resolved N packages, Installed N packages` (no errors).

Run: `cd apps/backend && uv run pytest -v`
Expected: `no tests ran` (no tests yet, but pytest discovers the package).

- [ ] **Step 6: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/.python-version \
  apps/backend/services/interpreter/__init__.py \
  apps/backend/tests/__init__.py apps/backend/tests/conftest.py
git commit -m "chore: scaffold backend project with pyproject and pytest"
```

---

## Task 2: Config module with env vars

**Files:**
- Create: `apps/backend/services/interpreter/config.py`
- Create: `apps/backend/tests/unit/__init__.py`
- Test: `apps/backend/tests/unit/test_config.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/__init__.py` (empty).

Create `apps/backend/tests/unit/test_config.py`:
```python
"""Unit tests for config loading."""
from __future__ import annotations

import pytest

from services.interpreter.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_REGION", "us-central1")
    monkeypatch.setenv("VERTEX_AI_ENDPOINT", "gemma-4-instruct")
    monkeypatch.setenv("GCS_BUCKET_ARTIFACTS", "test-bucket")

    settings = Settings()

    assert settings.gcp_project_id == "test-project"
    assert settings.gcp_region == "us-central1"
    assert settings.vertex_ai_endpoint == "gemma-4-instruct"
    assert settings.gemma_temperature == 0.2  # default
    assert settings.session_ttl_hours == 24  # default
    assert settings.rate_limit_per_minute == 30  # default


def test_settings_cors_origins_parsed_as_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("GCP_REGION", "r")
    monkeypatch.setenv("VERTEX_AI_ENDPOINT", "e")
    monkeypatch.setenv("GCS_BUCKET_ARTIFACTS", "b")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://a.vercel.app,https://b.vercel.app,http://localhost:3000",
    )

    settings = Settings()

    assert settings.cors_allowed_origins == [
        "https://a.vercel.app",
        "https://b.vercel.app",
        "http://localhost:3000",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.interpreter.config'`.

- [ ] **Step 3: Implement minimal config**

Create `apps/backend/services/interpreter/config.py`:
```python
"""Settings loaded from environment variables (Pydantic Settings)."""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the Interpreter service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GCP
    gcp_project_id: str
    gcp_region: str

    # Vertex AI / Gemma 4
    vertex_ai_endpoint: str
    gemma_temperature: float = 0.2
    gemma_max_tokens: int = 2048
    gemma_timeout_seconds: int = 10

    # CORS
    cors_allowed_origins: list[str] = Field(default_factory=list)

    # Session
    session_ttl_hours: int = 24
    session_max_retries: int = 5  # anomaly threshold

    # Rate limiting
    rate_limit_per_minute: int = 30

    # Storage
    gcs_bucket_artifacts: str
    signed_url_ttl_hours: int = 24

    # Degraded mode
    degraded_mode_failure_threshold: int = 2
    degraded_mode_duration_seconds: int = 60

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_config.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/config.py \
  apps/backend/tests/unit/__init__.py \
  apps/backend/tests/unit/test_config.py
git commit -m "feat(interpreter): add env-driven Settings with CORS parsing"
```

---

## Task 3: InterpreterError taxonomy

**Files:**
- Create: `apps/backend/services/interpreter/domain/__init__.py`
- Create: `apps/backend/services/interpreter/domain/errors.py`
- Test: `apps/backend/tests/unit/test_errors.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/services/interpreter/domain/__init__.py` (empty).

Create `apps/backend/tests/unit/test_errors.py`:
```python
"""Unit tests for InterpreterError taxonomy."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)


def test_error_code_stable_values() -> None:
    # These string values are part of the HTTP contract — do not change.
    assert ErrorCode.INVALID_JSON_RETRY_FAILED == "invalid_json_retry_failed"
    assert ErrorCode.UNKNOWN_PRIMITIVE == "unknown_primitive"
    assert ErrorCode.PHYSICAL_RANGE_VIOLATION == "physical_range_violation"
    assert ErrorCode.AMBIGUOUS_INTENT == "ambiguous_intent"
    assert ErrorCode.UNIT_PARSE_FAILED == "unit_parse_failed"
    assert ErrorCode.VERTEX_AI_TIMEOUT == "vertex_ai_timeout"
    assert ErrorCode.VERTEX_AI_RATE_LIMIT == "vertex_ai_rate_limit"
    assert ErrorCode.SESSION_NOT_FOUND == "session_not_found"
    assert ErrorCode.SESSION_EXPIRED == "session_expired"
    assert ErrorCode.INTERNAL_ERROR == "internal_error"


def test_interpreter_error_serializes_to_dict() -> None:
    err = InterpreterError(
        code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
        message="inner_diameter must be smaller than outer_diameter",
        field="inner_diameter_m",
    )

    assert err.model_dump() == {
        "code": "physical_range_violation",
        "message": "inner_diameter must be smaller than outer_diameter",
        "field": "inner_diameter_m",
        "details": None,
        "retry_after": None,
    }


def test_interpreter_error_raises_with_retry_after() -> None:
    err = InterpreterError(
        code=ErrorCode.VERTEX_AI_RATE_LIMIT,
        message="Rate limited",
        retry_after=30,
    )
    with pytest.raises(RuntimeError):
        err.raise_as()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.interpreter.domain.errors'`.

- [ ] **Step 3: Implement errors module**

Create `apps/backend/services/interpreter/domain/errors.py`:
```python
"""Error taxonomy for the Interpreter service.

Codes are part of the HTTP contract and MUST remain stable across versions.
User-facing messages are expected to be localized by the caller.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Stable error codes exposed via HTTP."""

    INVALID_JSON_RETRY_FAILED = "invalid_json_retry_failed"
    UNKNOWN_PRIMITIVE = "unknown_primitive"
    PHYSICAL_RANGE_VIOLATION = "physical_range_violation"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    UNIT_PARSE_FAILED = "unit_parse_failed"
    VERTEX_AI_TIMEOUT = "vertex_ai_timeout"
    VERTEX_AI_RATE_LIMIT = "vertex_ai_rate_limit"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_EXPIRED = "session_expired"
    INTERNAL_ERROR = "internal_error"


class InterpreterError(BaseModel):
    """Structured error returned to clients or raised internally."""

    code: ErrorCode
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None
    retry_after: int | None = Field(
        default=None,
        description="Seconds before the client should retry, if recoverable.",
    )

    def raise_as(self) -> None:
        """Raise this error as a RuntimeError carrying the model."""
        raise InterpreterException(self)


class InterpreterException(RuntimeError):
    """Python exception wrapping an InterpreterError for propagation."""

    def __init__(self, error: InterpreterError) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_errors.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/domain/ \
  apps/backend/tests/unit/test_errors.py
git commit -m "feat(interpreter): add InterpreterError taxonomy with 10 stable codes"
```

---

## Task 4: DesignIntent and TriStateField models

**Files:**
- Create: `apps/backend/services/interpreter/domain/intent.py`
- Test: `apps/backend/tests/unit/test_intent.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_intent.py`:
```python
"""Unit tests for DesignIntent and TriStateField."""
from __future__ import annotations

import pytest

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def test_extracted_field_has_value_and_no_reason() -> None:
    f = TriStateField(value=0.5, source=FieldSource.EXTRACTED)
    assert f.value == 0.5
    assert f.source == "extracted"
    assert f.reason is None
    assert f.required is False


def test_defaulted_field_requires_reason() -> None:
    with pytest.raises(ValueError, match="defaulted fields must include a reason"):
        TriStateField(value="steel_a36", source=FieldSource.DEFAULTED)


def test_missing_field_has_null_value_and_required_true() -> None:
    f = TriStateField(value=None, source=FieldSource.MISSING, required=True)
    assert f.value is None
    assert f.source == "missing"
    assert f.required is True


def test_missing_field_with_non_null_value_raises() -> None:
    with pytest.raises(ValueError, match="missing fields must have value=None"):
        TriStateField(value=0.5, source=FieldSource.MISSING, required=True)


def test_design_intent_roundtrip() -> None:
    intent = DesignIntent(
        type="flywheel",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(
                value=0.1, source=FieldSource.DEFAULTED, reason="common ratio 1:5"
            ),
            "rpm": TriStateField(value=3000, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(
                value=None, source=FieldSource.MISSING, required=True
            ),
        },
    )
    data = intent.model_dump()
    restored = DesignIntent.model_validate(data)
    assert restored == intent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_intent.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement intent module**

Create `apps/backend/services/interpreter/domain/intent.py`:
```python
"""DesignIntent and TriStateField — the output contract of the Interpreter."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator


class FieldSource(StrEnum):
    """Origin of a field value in a DesignIntent."""

    EXTRACTED = "extracted"  # LLM parsed it from user input
    DEFAULTED = "defaulted"  # LLM inferred a reasonable default
    MISSING = "missing"      # LLM could not determine; user must fill
    USER = "user"            # User explicitly set this via the form


class TriStateField(BaseModel):
    """A single field of a DesignIntent with provenance metadata."""

    model_config = ConfigDict(frozen=True)

    value: Any | None
    source: FieldSource
    reason: str | None = None
    required: bool = False
    original: str | None = None  # preserves user's original unit expression

    @model_validator(mode="after")
    def _validate_source_constraints(self) -> Self:
        if self.source == FieldSource.DEFAULTED and not self.reason:
            raise ValueError("defaulted fields must include a reason")
        if self.source == FieldSource.MISSING and self.value is not None:
            raise ValueError("missing fields must have value=None")
        return self


class DesignIntent(BaseModel):
    """The output of the Interpreter: a fully typed design specification."""

    model_config = ConfigDict(frozen=False)

    type: str                          # primitive name, e.g. "flywheel"
    fields: dict[str, TriStateField]
    composed_of: list[str] = []        # names of additional primitives composed

    def has_missing_fields(self) -> bool:
        return any(f.source == FieldSource.MISSING for f in self.fields.values())

    def missing_field_names(self) -> list[str]:
        return [
            name for name, f in self.fields.items()
            if f.source == FieldSource.MISSING
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_intent.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/domain/intent.py \
  apps/backend/tests/unit/test_intent.py
git commit -m "feat(interpreter): add DesignIntent and TriStateField models"
```

---

## Task 5: PrimitiveSchema + primitives registry

**Files:**
- Create: `apps/backend/services/interpreter/domain/primitives_registry.py`
- Test: `apps/backend/tests/unit/test_primitives_registry.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_primitives_registry.py`:
```python
"""Unit tests for the primitives registry."""
from __future__ import annotations

import pytest

from services.interpreter.domain.primitives_registry import (
    PARAM_TYPE_FLOAT,
    ParamSpec,
    PrimitiveSchema,
    PrimitivesRegistry,
)


@pytest.fixture
def registry() -> PrimitivesRegistry:
    return PrimitivesRegistry(
        [
            PrimitiveSchema(
                name="Flywheel_Rim",
                category="rotational",
                description="Rim with mass concentrated at periphery.",
                params={
                    "outer_diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.05, max=3.0, required=True
                    ),
                    "inner_diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.0, max=2.8, required=True
                    ),
                    "thickness_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.005, max=0.5, required=True
                    ),
                },
                composable_with=["Shaft"],
            ),
            PrimitiveSchema(
                name="Shaft",
                category="rotational",
                description="Cylindrical rotating element.",
                params={
                    "diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True
                    ),
                    "length_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.01, max=10.0, required=True
                    ),
                },
            ),
        ]
    )


def test_list_returns_all_summaries(registry: PrimitivesRegistry) -> None:
    summaries = registry.list_summaries()
    assert len(summaries) == 2
    assert summaries[0].name == "Flywheel_Rim"
    assert summaries[1].category == "rotational"


def test_get_by_name_returns_full_schema(registry: PrimitivesRegistry) -> None:
    schema = registry.get("Flywheel_Rim")
    assert schema.name == "Flywheel_Rim"
    assert "outer_diameter_m" in schema.params
    assert schema.params["outer_diameter_m"].min == 0.05


def test_get_unknown_raises_keyerror(registry: PrimitivesRegistry) -> None:
    with pytest.raises(KeyError, match="Unknown primitive: SuperFlywheel"):
        registry.get("SuperFlywheel")


def test_case_sensitive_lookup(registry: PrimitivesRegistry) -> None:
    with pytest.raises(KeyError):
        registry.get("flywheel_rim")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_primitives_registry.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement registry**

Create `apps/backend/services/interpreter/domain/primitives_registry.py`:
```python
"""Primitives registry — source of truth for what Gemma 4 can compose."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


PARAM_TYPE_FLOAT = "float"
PARAM_TYPE_INT = "int"
PARAM_TYPE_STRING = "string"
ParamType = Literal["float", "int", "string"]


class ParamSpec(BaseModel):
    """Specification of a single primitive parameter."""

    model_config = ConfigDict(frozen=True)

    type: ParamType
    min: float | None = None
    max: float | None = None
    required: bool = True
    description: str | None = None
    allowed_values: list[str] | None = None


class PrimitiveSchema(BaseModel):
    """Full schema of a single primitive exposed to Gemma 4."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: str  # e.g. "rotational", "structural", "articulated"
    description: str
    params: dict[str, ParamSpec]
    composable_with: list[str] = []


class PrimitiveSummary(BaseModel):
    """Lightweight summary returned by list_primitives()."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: str
    description: str


class PrimitivesRegistry:
    """In-memory registry of primitives. Populated from Python code."""

    def __init__(self, schemas: list[PrimitiveSchema]) -> None:
        self._schemas = {s.name: s for s in schemas}

    def list_summaries(self) -> list[PrimitiveSummary]:
        return [
            PrimitiveSummary(
                name=s.name, category=s.category, description=s.description
            )
            for s in self._schemas.values()
        ]

    def get(self, name: str) -> PrimitiveSchema:
        if name not in self._schemas:
            raise KeyError(f"Unknown primitive: {name}")
        return self._schemas[name]

    def names(self) -> set[str]:
        return set(self._schemas.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_primitives_registry.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Add the hackathon's 7 initial primitives (module-level default)**

Append to `apps/backend/services/interpreter/domain/primitives_registry.py`:
```python
def _build_default_registry() -> PrimitivesRegistry:
    """Initial primitives covering the 3 hero demos."""
    return PrimitivesRegistry([
        PrimitiveSchema(
            name="Flywheel_Rim",
            category="rotational",
            description="Rim with mass concentrated at the periphery for energy storage.",
            params={
                "outer_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.05, max=3.0, required=True,
                    description="Outer rim diameter in meters.",
                ),
                "inner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.0, max=2.8, required=True,
                    description="Inner hole diameter in meters.",
                ),
                "thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.005, max=0.5, required=True,
                    description="Axial thickness of the rim in meters.",
                ),
                "rpm": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=10, max=60000, required=True,
                    description="Rotational speed in revolutions per minute.",
                ),
            },
            composable_with=["Shaft", "Bearing_Housing"],
        ),
        PrimitiveSchema(
            name="Shaft",
            category="rotational",
            description="Cylindrical rotating element transmitting torque.",
            params={
                "diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True,
                ),
                "length_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.01, max=10.0, required=True,
                ),
            },
            composable_with=["Flywheel_Rim", "Pelton_Runner", "Bearing_Housing"],
        ),
        PrimitiveSchema(
            name="Bearing_Housing",
            category="structural",
            description="Support housing for a shaft bearing.",
            params={
                "bore_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True,
                ),
                "outer_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.01, max=2.0, required=True,
                ),
            },
            composable_with=["Shaft"],
        ),
        PrimitiveSchema(
            name="Pelton_Runner",
            category="rotational",
            description="Simplified Pelton hydro-turbine runner.",
            params={
                "runner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=5.0, required=True,
                ),
                "bucket_count": ParamSpec(
                    type=PARAM_TYPE_INT, min=12, max=30, required=True,
                ),
            },
            composable_with=["Shaft", "Housing", "Mounting_Frame"],
        ),
        PrimitiveSchema(
            name="Housing",
            category="structural",
            description="Enclosure around rotating machinery.",
            params={
                "inner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=5.0, required=True,
                ),
                "wall_thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.002, max=0.1, required=True,
                ),
            },
            composable_with=["Pelton_Runner", "Mounting_Frame"],
        ),
        PrimitiveSchema(
            name="Mounting_Frame",
            category="structural",
            description="Modular base frame for mounting machinery.",
            params={
                "length_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.2, max=5.0, required=True,
                ),
                "width_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.2, max=3.0, required=True,
                ),
                "height_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.05, max=1.0, required=True,
                ),
            },
        ),
        PrimitiveSchema(
            name="Hinge_Panel",
            category="articulated",
            description="Rigid panel hinged at one edge, used in foldable structures.",
            params={
                "width_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=4.0, required=True,
                ),
                "height_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=3.0, required=True,
                ),
                "thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.005, max=0.05, required=True,
                ),
            },
            composable_with=["Tensor_Rod", "Base_Connector"],
        ),
    ])


DEFAULT_REGISTRY = _build_default_registry()
```

- [ ] **Step 6: Add test for default registry**

Append to `apps/backend/tests/unit/test_primitives_registry.py`:
```python
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY


def test_default_registry_contains_hero_demo_primitives() -> None:
    names = DEFAULT_REGISTRY.names()
    # Hero 1 — Flywheel
    assert "Flywheel_Rim" in names
    assert "Shaft" in names
    assert "Bearing_Housing" in names
    # Hero 2 — Hydroelectric
    assert "Pelton_Runner" in names
    assert "Housing" in names
    assert "Mounting_Frame" in names
    # Hero 3 — Shelter
    assert "Hinge_Panel" in names
```

Run: `cd apps/backend && uv run pytest tests/unit/test_primitives_registry.py -v`
Expected: 5 PASSED.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/interpreter/domain/primitives_registry.py \
  apps/backend/tests/unit/test_primitives_registry.py
git commit -m "feat(interpreter): add PrimitivesRegistry with 7 hero-demo primitives"
```

---

## Task 6: Physical range validators

**Files:**
- Create: `apps/backend/services/interpreter/domain/validators.py`
- Test: `apps/backend/tests/unit/test_validators.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_validators.py`:
```python
"""Unit tests for physical range validators."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.domain.validators import validate_physical_consistency


def _field(value: float | int | str, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


def test_valid_flywheel_passes() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise


def test_inner_diameter_not_smaller_than_outer_raises() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.6),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "inner_diameter_m"


def test_value_below_range_raises() -> None:
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": _field(0.0005),  # min is 0.001
            "length_m": _field(0.5),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "diameter_m"


def test_value_above_range_raises() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(100000),  # max is 60000
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.field == "rpm"


def test_unknown_primitive_raises_unknown_primitive_error() -> None:
    intent = DesignIntent(
        type="SuperFlywheel",
        fields={"outer_diameter_m": _field(0.5)},
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.UNKNOWN_PRIMITIVE


def test_missing_fields_are_not_validated_for_range() -> None:
    # Missing fields are expected during extraction; they skip range check.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": TriStateField(value=None, source=FieldSource.MISSING, required=True),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise


def test_required_field_absent_raises() -> None:
    # thickness_m is required but absent from fields dict entirely.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "rpm": _field(3000),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "thickness_m"


def test_unknown_param_name_is_ignored() -> None:
    # Extra fields from LLM hallucination should NOT fail validation;
    # they are simply ignored in range checks.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
            "magical_field": _field("unknown"),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_validators.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement validators**

Create `apps/backend/services/interpreter/domain/validators.py`:
```python
"""Physical range and cross-field consistency validators for DesignIntent."""
from __future__ import annotations

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
    InterpreterException,
)
from services.interpreter.domain.intent import DesignIntent, FieldSource
from services.interpreter.domain.primitives_registry import (
    PrimitiveSchema,
    PrimitivesRegistry,
)


# Cross-field consistency rules per primitive type.
_CROSS_FIELD_RULES: dict[str, list[tuple[str, str, str]]] = {
    # (field_a, field_b, relation) — enforces field_a < field_b.
    "Flywheel_Rim": [("inner_diameter_m", "outer_diameter_m", "<")],
}


def validate_physical_consistency(
    intent: DesignIntent, registry: PrimitivesRegistry
) -> None:
    """Validate `intent` against `registry`. Raises InterpreterException on failure."""
    try:
        schema = registry.get(intent.type)
    except KeyError:
        InterpreterError(
            code=ErrorCode.UNKNOWN_PRIMITIVE,
            message=f"Primitive '{intent.type}' is not registered.",
            field=None,
            details={"type": intent.type},
        ).raise_as()

    _validate_required_fields_present(intent, schema)
    _validate_field_ranges(intent, schema)
    _validate_cross_field_consistency(intent)


def _validate_required_fields_present(
    intent: DesignIntent, schema: PrimitiveSchema
) -> None:
    for name, spec in schema.params.items():
        if not spec.required:
            continue
        if name not in intent.fields:
            InterpreterError(
                code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                message=f"Required field '{name}' is absent.",
                field=name,
            ).raise_as()


def _validate_field_ranges(intent: DesignIntent, schema: PrimitiveSchema) -> None:
    for name, field in intent.fields.items():
        if name not in schema.params:
            continue  # Unknown params from LLM are tolerated, not validated.
        if field.source == FieldSource.MISSING:
            continue
        spec = schema.params[name]
        if spec.type in ("float", "int"):
            value = field.value
            if not isinstance(value, int | float):
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=f"Field '{name}' must be numeric.",
                    field=name,
                ).raise_as()
            if spec.min is not None and value < spec.min:
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=(
                        f"Field '{name}' value {value} is below minimum {spec.min}."
                    ),
                    field=name,
                ).raise_as()
            if spec.max is not None and value > spec.max:
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=(
                        f"Field '{name}' value {value} exceeds maximum {spec.max}."
                    ),
                    field=name,
                ).raise_as()


def _validate_cross_field_consistency(intent: DesignIntent) -> None:
    rules = _CROSS_FIELD_RULES.get(intent.type, [])
    for a, b, relation in rules:
        fa = intent.fields.get(a)
        fb = intent.fields.get(b)
        if fa is None or fb is None:
            continue
        if fa.source == FieldSource.MISSING or fb.source == FieldSource.MISSING:
            continue
        va, vb = fa.value, fb.value
        if relation == "<" and not (va < vb):
            InterpreterError(
                code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                message=f"'{a}' must be less than '{b}' (got {va} vs {vb}).",
                field=a,
            ).raise_as()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_validators.py -v`
Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/domain/validators.py \
  apps/backend/tests/unit/test_validators.py
git commit -m "feat(interpreter): add physical range and cross-field validators"
```

---

## Task 7: Unit normalizer with pint

**Files:**
- Create: `apps/backend/services/interpreter/normalizer/__init__.py`
- Create: `apps/backend/services/interpreter/normalizer/units.py`
- Test: `apps/backend/tests/unit/test_normalizer.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/services/interpreter/normalizer/__init__.py` (empty).

Create `apps/backend/tests/unit/test_normalizer.py`:
```python
"""Unit tests for the unit normalizer."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.normalizer.units import NormalizedValue, normalize


def test_metric_meters_passthrough() -> None:
    r = normalize("0.5 m")
    assert r == NormalizedValue(value=0.5, unit_si="m", original="0.5 m")


def test_metric_centimeters_to_meters() -> None:
    r = normalize("25 cm")
    assert r.value == pytest.approx(0.25)
    assert r.unit_si == "m"


def test_metric_millimeters_to_meters() -> None:
    r = normalize("50 mm")
    assert r.value == pytest.approx(0.05)


def test_imperial_inches_to_meters() -> None:
    r = normalize("10 inches")
    assert r.value == pytest.approx(0.254)
    assert r.unit_si == "m"


def test_imperial_feet_to_meters() -> None:
    r = normalize("3 ft")
    assert r.value == pytest.approx(0.9144)


def test_imperial_pounds_to_kg() -> None:
    r = normalize("10 lb")
    assert r.value == pytest.approx(4.5359237)
    assert r.unit_si == "kg"


def test_rpm_preserved_as_compound_unit() -> None:
    # RPM is not an SI unit but is a canonical engineering unit we keep as-is.
    r = normalize("3000 rpm")
    assert r.value == 3000.0
    assert r.unit_si == "rpm"


def test_psi_to_pascal() -> None:
    r = normalize("100 psi")
    assert r.value == pytest.approx(689475.7, rel=1e-4)
    assert r.unit_si == "Pa"


def test_pure_number_no_unit_returns_dimensionless() -> None:
    r = normalize("42")
    assert r.value == 42.0
    assert r.unit_si == ""  # dimensionless marker


def test_invalid_unit_raises() -> None:
    with pytest.raises(InterpreterException) as exc:
        normalize("3 platypus")
    assert exc.value.error.code == ErrorCode.UNIT_PARSE_FAILED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_normalizer.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement normalizer**

Create `apps/backend/services/interpreter/normalizer/units.py`:
```python
"""Parse arbitrary unit expressions and normalize to SI.

Uses `pint` as the underlying unit library. Dimensionless quantities
(pure numbers) return an empty unit_si string. RPM is treated as a
canonical engineering unit and kept as-is (not converted to rad/s).
"""
from __future__ import annotations

from dataclasses import dataclass

import pint

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)


_UREG = pint.UnitRegistry()

# Mapping of canonical SI base units used as the output unit_si string.
_SI_OUTPUT_MAP: dict[str, str] = {
    "meter": "m",
    "kilogram": "kg",
    "second": "s",
    "kelvin": "K",
    "pascal": "Pa",
    "newton": "N",
    "joule": "J",
    "watt": "W",
}

# Units we keep as-is (no conversion), by canonical pint name.
_NON_SI_KEPT_AS_IS: set[str] = {"revolutions_per_minute"}


@dataclass(frozen=True)
class NormalizedValue:
    """A scalar value in SI with its original expression preserved."""

    value: float
    unit_si: str
    original: str


def normalize(expression: str) -> NormalizedValue:
    """Parse `expression` and convert to SI. Raises InterpreterException on failure."""
    try:
        quantity = _UREG.Quantity(expression)
    except (
        pint.errors.UndefinedUnitError,
        pint.errors.DimensionalityError,
        ValueError,
    ) as e:
        InterpreterError(
            code=ErrorCode.UNIT_PARSE_FAILED,
            message=f"Could not parse '{expression}' as a valid unit expression.",
            details={"error": str(e)},
        ).raise_as()

    # Dimensionless (pure number)
    if quantity.dimensionless:
        return NormalizedValue(
            value=float(quantity.magnitude), unit_si="", original=expression
        )

    # Keep RPM-like units as-is
    canonical = str(quantity.units)
    if canonical in _NON_SI_KEPT_AS_IS:
        return NormalizedValue(
            value=float(quantity.magnitude),
            unit_si="rpm",
            original=expression,
        )

    # Convert to SI base units
    try:
        si_quantity = quantity.to_base_units()
    except pint.errors.DimensionalityError as e:
        InterpreterError(
            code=ErrorCode.UNIT_PARSE_FAILED,
            message=f"Cannot convert '{expression}' to SI base units.",
            details={"error": str(e)},
        ).raise_as()

    unit_key = str(si_quantity.units).split(" ")[0]
    unit_si = _SI_OUTPUT_MAP.get(unit_key, str(si_quantity.units))
    return NormalizedValue(
        value=float(si_quantity.magnitude),
        unit_si=unit_si,
        original=expression,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_normalizer.py -v`
Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/normalizer/ \
  apps/backend/tests/unit/test_normalizer.py
git commit -m "feat(interpreter): add pint-based unit normalizer to SI"
```

---

## Task 8: Session merge logic (pure)

**Files:**
- Create: `apps/backend/services/interpreter/session/__init__.py`
- Create: `apps/backend/services/interpreter/session/merge.py`
- Test: `apps/backend/tests/unit/test_session_merge.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/services/interpreter/session/__init__.py` (empty).

Create `apps/backend/tests/unit/test_session_merge.py`:
```python
"""Unit tests for session intent merging."""
from __future__ import annotations

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.merge import apply_user_overrides, merge_refinement


def _f(value: object, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


def test_user_override_wins_over_extracted() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": _f(0.5)},
    )
    overrides = {
        "outer_diameter_m": TriStateField(value=0.8, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    assert merged.fields["outer_diameter_m"].value == 0.8
    assert merged.fields["outer_diameter_m"].source == FieldSource.USER


def test_override_fills_missing_field() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": TriStateField(
                value=None, source=FieldSource.MISSING, required=True
            ),
        },
    )
    overrides = {
        "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    assert merged.fields["inner_diameter_m"].value == 0.1
    assert merged.fields["inner_diameter_m"].source == FieldSource.USER
    assert not merged.has_missing_fields()


def test_no_overrides_returns_same_intent() -> None:
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    merged = apply_user_overrides(intent, {})
    assert merged == intent


def test_merge_refinement_applies_field_updates_as_user_source() -> None:
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    updated = merge_refinement(intent, {"diameter_m": 0.08})
    assert updated.fields["diameter_m"].value == 0.08
    assert updated.fields["diameter_m"].source == FieldSource.USER
    # Unchanged field preserved.
    assert updated.fields["length_m"].value == 0.5


def test_merge_refinement_unknown_field_creates_user_entry() -> None:
    # If the user form sends a field not in the intent, we add it.
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    updated = merge_refinement(intent, {"material": "steel_a36"})
    assert updated.fields["material"].value == "steel_a36"
    assert updated.fields["material"].source == FieldSource.USER


def test_apply_user_overrides_is_immutable() -> None:
    intent = DesignIntent(type="Shaft", fields={"diameter_m": _f(0.05)})
    overrides = {
        "diameter_m": TriStateField(value=0.08, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    # Original intent is untouched.
    assert intent.fields["diameter_m"].value == 0.05
    assert merged.fields["diameter_m"].value == 0.08
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_session_merge.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement merge module**

Create `apps/backend/services/interpreter/session/merge.py`:
```python
"""Pure functions for merging user overrides into a DesignIntent.

These functions are deterministic and never call external services.
"""
from __future__ import annotations

from typing import Any

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def apply_user_overrides(
    intent: DesignIntent,
    overrides: dict[str, TriStateField],
) -> DesignIntent:
    """Return a new DesignIntent with user overrides applied.

    User overrides always win over LLM-inferred values. The original
    intent is not mutated.
    """
    if not overrides:
        return intent
    new_fields = dict(intent.fields)
    for name, override in overrides.items():
        new_fields[name] = override
    return DesignIntent(
        type=intent.type,
        fields=new_fields,
        composed_of=list(intent.composed_of),
    )


def merge_refinement(
    intent: DesignIntent,
    field_updates: dict[str, Any],
) -> DesignIntent:
    """Apply raw field updates from the refine endpoint.

    Each update is coerced into a TriStateField with source=USER.
    """
    overrides = {
        name: TriStateField(value=value, source=FieldSource.USER)
        for name, value in field_updates.items()
    }
    return apply_user_overrides(intent, overrides)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_session_merge.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/session/ \
  apps/backend/tests/unit/test_session_merge.py
git commit -m "feat(interpreter): add pure session merge for user overrides"
```

---

## Task 9: Materials catalog + loader

**Files:**
- Create: `apps/backend/data/materials.json`
- Create: `apps/backend/services/interpreter/domain/materials.py`
- Test: `apps/backend/tests/unit/test_materials_loader.py`

- [ ] **Step 1: Create seed materials.json**

Create `apps/backend/data/materials.json`:
```json
{
  "version": 1,
  "materials": [
    {
      "name": "steel_a36",
      "display_name": "Steel A36",
      "category": "metal",
      "density_kg_m3": 7850,
      "young_modulus_gpa": 200,
      "yield_strength_mpa": 250,
      "ultimate_tensile_strength_mpa": 400,
      "thermal_conductivity_w_m_k": 51,
      "max_service_temperature_c": 400,
      "relative_cost_index": 1.0,
      "sustainability_score": 0.5
    },
    {
      "name": "aluminum_6061",
      "display_name": "Aluminum 6061-T6",
      "category": "metal",
      "density_kg_m3": 2700,
      "young_modulus_gpa": 69,
      "yield_strength_mpa": 276,
      "ultimate_tensile_strength_mpa": 310,
      "thermal_conductivity_w_m_k": 167,
      "max_service_temperature_c": 200,
      "relative_cost_index": 2.5,
      "sustainability_score": 0.7
    },
    {
      "name": "stainless_304",
      "display_name": "Stainless Steel 304",
      "category": "metal",
      "density_kg_m3": 8000,
      "young_modulus_gpa": 193,
      "yield_strength_mpa": 215,
      "ultimate_tensile_strength_mpa": 505,
      "thermal_conductivity_w_m_k": 16,
      "max_service_temperature_c": 800,
      "relative_cost_index": 3.0,
      "sustainability_score": 0.4
    },
    {
      "name": "titanium_grade2",
      "display_name": "Titanium Grade 2",
      "category": "metal",
      "density_kg_m3": 4500,
      "young_modulus_gpa": 103,
      "yield_strength_mpa": 275,
      "ultimate_tensile_strength_mpa": 345,
      "thermal_conductivity_w_m_k": 17,
      "max_service_temperature_c": 550,
      "relative_cost_index": 20.0,
      "sustainability_score": 0.3
    },
    {
      "name": "abs",
      "display_name": "ABS Plastic",
      "category": "polymer",
      "density_kg_m3": 1040,
      "young_modulus_gpa": 2.3,
      "yield_strength_mpa": 40,
      "ultimate_tensile_strength_mpa": 40,
      "thermal_conductivity_w_m_k": 0.17,
      "max_service_temperature_c": 80,
      "relative_cost_index": 0.5,
      "sustainability_score": 0.2
    },
    {
      "name": "pla_biodegradable",
      "display_name": "PLA (biodegradable)",
      "category": "polymer",
      "density_kg_m3": 1250,
      "young_modulus_gpa": 3.5,
      "yield_strength_mpa": 60,
      "ultimate_tensile_strength_mpa": 65,
      "thermal_conductivity_w_m_k": 0.13,
      "max_service_temperature_c": 60,
      "relative_cost_index": 1.0,
      "sustainability_score": 0.95
    },
    {
      "name": "bamboo_laminated",
      "display_name": "Laminated Bamboo",
      "category": "composite",
      "density_kg_m3": 700,
      "young_modulus_gpa": 12,
      "yield_strength_mpa": 50,
      "ultimate_tensile_strength_mpa": 140,
      "thermal_conductivity_w_m_k": 0.17,
      "max_service_temperature_c": 120,
      "relative_cost_index": 0.8,
      "sustainability_score": 0.98
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

Create `apps/backend/tests/unit/test_materials_loader.py`:
```python
"""Unit tests for the materials catalog loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.domain.materials import (
    MaterialProperties,
    MaterialsCatalog,
    load_catalog,
)


@pytest.fixture
def catalog() -> MaterialsCatalog:
    root = Path(__file__).parent.parent.parent / "data"
    return load_catalog(root / "materials.json")


def test_catalog_has_seed_materials(catalog: MaterialsCatalog) -> None:
    names = catalog.names()
    assert "steel_a36" in names
    assert "aluminum_6061" in names
    assert "pla_biodegradable" in names
    assert "bamboo_laminated" in names
    assert len(names) >= 7


def test_get_material_returns_properties(catalog: MaterialsCatalog) -> None:
    mat = catalog.get("steel_a36")
    assert isinstance(mat, MaterialProperties)
    assert mat.density_kg_m3 == 7850
    assert mat.yield_strength_mpa == 250


def test_get_unknown_raises_keyerror(catalog: MaterialsCatalog) -> None:
    with pytest.raises(KeyError, match="Unknown material: unobtanium"):
        catalog.get("unobtanium")


def test_search_by_category(catalog: MaterialsCatalog) -> None:
    metals = catalog.search(category="metal")
    names = {m.name for m in metals}
    assert "steel_a36" in names
    assert "aluminum_6061" in names
    assert "pla_biodegradable" not in names


def test_search_by_sustainability(catalog: MaterialsCatalog) -> None:
    sustainable = catalog.search(min_sustainability=0.9)
    names = {m.name for m in sustainable}
    assert "pla_biodegradable" in names
    assert "bamboo_laminated" in names
    assert "steel_a36" not in names


def test_search_by_max_density(catalog: MaterialsCatalog) -> None:
    light = catalog.search(max_density_kg_m3=2000)
    for m in light:
        assert m.density_kg_m3 <= 2000
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_materials_loader.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 4: Implement materials module**

Create `apps/backend/services/interpreter/domain/materials.py`:
```python
"""Materials catalog loaded from a local JSON file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


MaterialCategory = Literal["metal", "polymer", "composite", "ceramic"]


class MaterialProperties(BaseModel):
    """Full properties of a single material (SI units throughout)."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    category: MaterialCategory
    density_kg_m3: float
    young_modulus_gpa: float
    yield_strength_mpa: float
    ultimate_tensile_strength_mpa: float
    thermal_conductivity_w_m_k: float
    max_service_temperature_c: float
    relative_cost_index: float
    sustainability_score: float  # 0..1


class MaterialRef(BaseModel):
    """Lightweight reference returned by search_materials()."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    category: MaterialCategory
    density_kg_m3: float
    sustainability_score: float


class MaterialsCatalog:
    """In-memory catalog of materials, loaded at service startup."""

    def __init__(self, materials: list[MaterialProperties]) -> None:
        self._by_name = {m.name: m for m in materials}

    def names(self) -> set[str]:
        return set(self._by_name.keys())

    def get(self, name: str) -> MaterialProperties:
        if name not in self._by_name:
            raise KeyError(f"Unknown material: {name}")
        return self._by_name[name]

    def search(
        self,
        *,
        category: MaterialCategory | None = None,
        max_density_kg_m3: float | None = None,
        min_yield_strength_mpa: float | None = None,
        min_sustainability: float | None = None,
    ) -> list[MaterialRef]:
        results: list[MaterialRef] = []
        for m in self._by_name.values():
            if category is not None and m.category != category:
                continue
            if max_density_kg_m3 is not None and m.density_kg_m3 > max_density_kg_m3:
                continue
            if (
                min_yield_strength_mpa is not None
                and m.yield_strength_mpa < min_yield_strength_mpa
            ):
                continue
            if (
                min_sustainability is not None
                and m.sustainability_score < min_sustainability
            ):
                continue
            results.append(
                MaterialRef(
                    name=m.name,
                    display_name=m.display_name,
                    category=m.category,
                    density_kg_m3=m.density_kg_m3,
                    sustainability_score=m.sustainability_score,
                )
            )
        return results


def load_catalog(path: Path) -> MaterialsCatalog:
    """Load a MaterialsCatalog from a JSON file at `path`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = [MaterialProperties.model_validate(m) for m in data["materials"]]
    return MaterialsCatalog(materials)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_materials_loader.py -v`
Expected: 6 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/data/materials.json \
  apps/backend/services/interpreter/domain/materials.py \
  apps/backend/tests/unit/test_materials_loader.py
git commit -m "feat(interpreter): add materials catalog with 7 seed materials"
```

---

## Task 10: Tool implementations (primitives and materials)

**Files:**
- Create: `apps/backend/services/interpreter/tools/__init__.py`
- Create: `apps/backend/services/interpreter/tools/primitives.py`
- Create: `apps/backend/services/interpreter/tools/materials.py`
- Create: `apps/backend/services/interpreter/tools/registry.py`
- Create: `apps/backend/tests/component/__init__.py`
- Test: `apps/backend/tests/component/test_tools.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/component/__init__.py` (empty).

Create `apps/backend/tests/component/test_tools.py`:
```python
"""Component tests for the 4 Gemma 4 tools."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import (
    build_materials_tools,
    get_material_properties,
    search_materials,
)
from services.interpreter.tools.primitives import (
    build_primitives_tools,
    get_primitive_schema,
    list_primitives,
)
from services.interpreter.tools.registry import ToolRegistry


@pytest.fixture
def catalog():
    root = Path(__file__).parent.parent.parent / "data"
    return load_catalog(root / "materials.json")


def test_list_primitives_returns_all_registered() -> None:
    result = list_primitives(DEFAULT_REGISTRY)
    names = [s["name"] for s in result]
    assert "Flywheel_Rim" in names
    assert "Pelton_Runner" in names


def test_get_primitive_schema_returns_full_params() -> None:
    result = get_primitive_schema(DEFAULT_REGISTRY, name="Flywheel_Rim")
    assert result["name"] == "Flywheel_Rim"
    assert "outer_diameter_m" in result["params"]
    assert result["params"]["outer_diameter_m"]["min"] == 0.05


def test_get_primitive_schema_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_primitive_schema(DEFAULT_REGISTRY, name="SuperFlywheel")


def test_search_materials_filters_correctly(catalog) -> None:
    result = search_materials(catalog, criteria={"category": "metal"})
    assert len(result) >= 3
    for m in result:
        assert m["category"] == "metal"


def test_get_material_properties_returns_full(catalog) -> None:
    result = get_material_properties(catalog, name="aluminum_6061")
    assert result["density_kg_m3"] == 2700
    assert result["yield_strength_mpa"] == 276


def test_registry_dispatches_by_name(catalog) -> None:
    registry = ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )
    assert set(registry.names()) == {
        "list_primitives",
        "get_primitive_schema",
        "search_materials",
        "get_material_properties",
    }
    result = registry.invoke("get_primitive_schema", {"name": "Shaft"})
    assert result["name"] == "Shaft"


def test_registry_unknown_tool_raises(catalog) -> None:
    registry = ToolRegistry(tools=build_primitives_tools(DEFAULT_REGISTRY))
    with pytest.raises(KeyError, match="Unknown tool: make_coffee"):
        registry.invoke("make_coffee", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/component/test_tools.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement primitives tools**

Create `apps/backend/services/interpreter/tools/__init__.py` (empty).

Create `apps/backend/services/interpreter/tools/primitives.py`:
```python
"""Gemma 4 tools for primitive discovery and schema retrieval."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.interpreter.domain.primitives_registry import PrimitivesRegistry


def list_primitives(registry: PrimitivesRegistry) -> list[dict[str, Any]]:
    """Tool: return a summary of every registered primitive."""
    return [s.model_dump() for s in registry.list_summaries()]


def get_primitive_schema(
    registry: PrimitivesRegistry, *, name: str
) -> dict[str, Any]:
    """Tool: return the full schema of primitive `name`."""
    return registry.get(name).model_dump()


def build_primitives_tools(
    registry: PrimitivesRegistry,
) -> dict[str, Callable[..., Any]]:
    """Return tool callables bound to the given registry."""
    return {
        "list_primitives": lambda args: list_primitives(registry),
        "get_primitive_schema": lambda args: get_primitive_schema(
            registry, name=args["name"]
        ),
    }
```

- [ ] **Step 4: Implement materials tools**

Create `apps/backend/services/interpreter/tools/materials.py`:
```python
"""Gemma 4 tools for material search and property lookup."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.interpreter.domain.materials import MaterialsCatalog


def search_materials(
    catalog: MaterialsCatalog, *, criteria: dict[str, Any]
) -> list[dict[str, Any]]:
    """Tool: filter the materials catalog by criteria."""
    refs = catalog.search(
        category=criteria.get("category"),
        max_density_kg_m3=criteria.get("max_density_kg_m3"),
        min_yield_strength_mpa=criteria.get("min_yield_strength_mpa"),
        min_sustainability=criteria.get("min_sustainability"),
    )
    return [r.model_dump() for r in refs]


def get_material_properties(
    catalog: MaterialsCatalog, *, name: str
) -> dict[str, Any]:
    """Tool: return full properties of material `name`."""
    return catalog.get(name).model_dump()


def build_materials_tools(
    catalog: MaterialsCatalog,
) -> dict[str, Callable[..., Any]]:
    """Return tool callables bound to the given catalog."""
    return {
        "search_materials": lambda args: search_materials(
            catalog, criteria=args.get("criteria", {})
        ),
        "get_material_properties": lambda args: get_material_properties(
            catalog, name=args["name"]
        ),
    }
```

- [ ] **Step 5: Implement ToolRegistry**

Create `apps/backend/services/interpreter/tools/registry.py`:
```python
"""Tool registry: single dispatch point for LLM-initiated tool calls."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolRegistry(BaseModel):
    """Maps tool names to their implementations. LLM cannot escape this set."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tools: dict[str, Callable[[dict[str, Any]], Any]]

    def names(self) -> list[str]:
        return sorted(self.tools.keys())

    def invoke(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self.tools:
            raise KeyError(f"Unknown tool: {name}")
        return self.tools[name](args)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/component/test_tools.py -v`
Expected: 7 PASSED.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/interpreter/tools/ \
  apps/backend/tests/component/test_tools.py \
  apps/backend/tests/component/__init__.py
git commit -m "feat(interpreter): add 4 Gemma 4 tools and ToolRegistry dispatcher"
```

---

## Task 11: Firestore session store with local fake

**Files:**
- Create: `apps/backend/services/interpreter/session/store.py`
- Create: `apps/backend/services/interpreter/session/fake_store.py`
- Test: `apps/backend/tests/unit/test_session_store.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_session_store.py`:
```python
"""Unit tests for the session store contract (using the local fake)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.fake_store import FakeSessionStore
from services.interpreter.session.store import Session, SessionMessage


@pytest.fixture
def store() -> FakeSessionStore:
    return FakeSessionStore()


async def test_create_and_load_session(store: FakeSessionStore) -> None:
    session = await store.create_session(
        user_id="anonymous", language="en"
    )
    assert session.session_id
    loaded = await store.load(session.session_id)
    assert loaded.session_id == session.session_id
    assert loaded.language == "en"


async def test_load_unknown_session_raises(store: FakeSessionStore) -> None:
    with pytest.raises(InterpreterException) as exc:
        await store.load("nonexistent")
    assert exc.value.error.code == ErrorCode.SESSION_NOT_FOUND


async def test_append_message_persists(store: FakeSessionStore) -> None:
    session = await store.create_session(user_id="u1", language="es")
    await store.append_message(
        session.session_id,
        SessionMessage(
            role="user",
            content="hola",
            timestamp=datetime.now(UTC),
        ),
    )
    loaded = await store.load(session.session_id)
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "hola"


async def test_update_intent_persists(store: FakeSessionStore) -> None:
    session = await store.create_session(user_id="u1", language="en")
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
    )
    await store.update_intent(session.session_id, intent, user_overrides={})
    loaded = await store.load(session.session_id)
    assert loaded.current_intent is not None
    assert loaded.current_intent.type == "Shaft"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_session_store.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement Session model and Store protocol**

Create `apps/backend/services/interpreter/session/store.py`:
```python
"""Session store contract and Firestore implementation."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from services.interpreter.domain.intent import DesignIntent, TriStateField


class SessionMessage(BaseModel):
    """A single message in a session conversation history."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict] | None = None
    timestamp: datetime


class Session(BaseModel):
    """Persistent session state."""

    model_config = ConfigDict(frozen=False)

    session_id: str
    user_id: str
    language: Literal["es", "en"]
    created_at: datetime
    updated_at: datetime
    messages: list[SessionMessage] = []
    current_intent: DesignIntent | None = None
    user_overrides: dict[str, TriStateField] = {}


class SessionStore(Protocol):
    """Async session persistence contract."""

    async def create_session(
        self, *, user_id: str, language: Literal["es", "en"]
    ) -> Session: ...

    async def load(self, session_id: str) -> Session: ...

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None: ...

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None: ...

    async def delete(self, session_id: str) -> None: ...
```

- [ ] **Step 4: Implement FakeSessionStore for testing**

Create `apps/backend/services/interpreter/session/fake_store.py`:
```python
"""In-memory implementation of SessionStore for unit/component tests."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)
from services.interpreter.domain.intent import DesignIntent, TriStateField
from services.interpreter.session.store import Session, SessionMessage


class FakeSessionStore:
    """Thread-unsafe in-memory session store for tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self, *, user_id: str, language: Literal["es", "en"]
    ) -> Session:
        now = datetime.now(UTC)
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            language=language,
            created_at=now,
            updated_at=now,
        )
        self._sessions[session.session_id] = session
        return session

    async def load(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        return self._sessions[session_id]

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None:
        session = await self.load(session_id)
        session.messages.append(message)
        session.updated_at = datetime.now(UTC)

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None:
        session = await self.load(session_id)
        session.current_intent = intent
        session.user_overrides = dict(user_overrides)
        session.updated_at = datetime.now(UTC)

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/unit/test_session_store.py -v`
Expected: 4 PASSED.

- [ ] **Step 6: Implement FirestoreSessionStore (real)**

Append to `apps/backend/services/interpreter/session/store.py`:
```python
# --- Firestore implementation ---
from datetime import UTC
from typing import Any
import uuid

from google.cloud import firestore  # type: ignore[import-untyped]

from services.interpreter.domain.errors import (  # noqa: E402
    ErrorCode,
    InterpreterError,
)


class FirestoreSessionStore:
    """Google Firestore-backed implementation of SessionStore."""

    COLLECTION = "interpreter_sessions"

    def __init__(self, client: firestore.AsyncClient) -> None:
        self._client = client

    def _collection(self) -> Any:
        return self._client.collection(self.COLLECTION)

    async def create_session(
        self, *, user_id: str, language: Literal["es", "en"]
    ) -> Session:
        now = datetime.now(UTC)
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            language=language,
            created_at=now,
            updated_at=now,
        )
        await self._collection().document(session.session_id).set(
            session.model_dump(mode="json")
        )
        return session

    async def load(self, session_id: str) -> Session:
        doc = await self._collection().document(session_id).get()
        if not doc.exists:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        return Session.model_validate(doc.to_dict())

    async def append_message(
        self, session_id: str, message: SessionMessage
    ) -> None:
        ref = self._collection().document(session_id)
        snap = await ref.get()
        if not snap.exists:
            InterpreterError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session '{session_id}' does not exist.",
            ).raise_as()
        await ref.update(
            {
                "messages": firestore.ArrayUnion(
                    [message.model_dump(mode="json")]
                ),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    async def update_intent(
        self,
        session_id: str,
        intent: DesignIntent,
        user_overrides: dict[str, TriStateField],
    ) -> None:
        await self._collection().document(session_id).update(
            {
                "current_intent": intent.model_dump(mode="json"),
                "user_overrides": {
                    k: v.model_dump(mode="json") for k, v in user_overrides.items()
                },
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    async def delete(self, session_id: str) -> None:
        await self._collection().document(session_id).delete()
```

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/interpreter/session/store.py \
  apps/backend/services/interpreter/session/fake_store.py \
  apps/backend/tests/unit/test_session_store.py
git commit -m "feat(interpreter): add session store with Firestore and in-memory fake"
```

---

## Task 12: Structured logging + tracing + metrics

**Files:**
- Create: `apps/backend/services/interpreter/observability/__init__.py`
- Create: `apps/backend/services/interpreter/observability/logging.py`
- Create: `apps/backend/services/interpreter/observability/metrics.py`
- Test: `apps/backend/tests/unit/test_observability.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/services/interpreter/observability/__init__.py` (empty).

Create `apps/backend/tests/unit/test_observability.py`:
```python
"""Unit tests for observability: logging and metrics."""
from __future__ import annotations

import json
import logging

from services.interpreter.observability.logging import (
    configure_logging,
    get_logger,
    hash_prompt,
)
from services.interpreter.observability.metrics import (
    InterpreterMetrics,
)


def test_logger_emits_structured_json(
    caplog: pytest.LogCaptureFixture,  # noqa: F821
) -> None:
    configure_logging(level="INFO", json_output=True)
    log = get_logger("interpreter.test")

    with caplog.at_level(logging.INFO):
        log.info("interpret_request", session_id="abc", latency_ms=123)

    record = caplog.records[-1]
    payload = json.loads(record.message) if record.message.startswith("{") else {
        "event": record.message
    }
    # structlog renders final JSON string via the processor — we accept either.
    assert "interpret_request" in record.message or payload.get(
        "event"
    ) == "interpret_request"


def test_hash_prompt_is_stable_and_not_plain_text() -> None:
    h1 = hash_prompt("Design a flywheel at 3000 RPM")
    h2 = hash_prompt("Design a flywheel at 3000 RPM")
    h3 = hash_prompt("Design a flywheel at 3001 RPM")
    assert h1 == h2
    assert h1 != h3
    assert "flywheel" not in h1  # Must not leak prompt text.
    assert len(h1) == 64  # sha256 hex


def test_metrics_counters_increment() -> None:
    metrics = InterpreterMetrics()
    metrics.request_count_inc(status="success", language="es", intent_type="flywheel")
    metrics.request_count_inc(status="success", language="es", intent_type="flywheel")
    metrics.retry_count_inc(error_code="invalid_json_retry_failed")

    snapshot = metrics.snapshot()
    assert snapshot["interpret.request_count"]["success|es|flywheel"] == 2
    assert snapshot["interpret.retry_count"]["invalid_json_retry_failed"] == 1


def test_metrics_latency_recording() -> None:
    metrics = InterpreterMetrics()
    metrics.latency_ms_record(intent_type="flywheel", value_ms=100)
    metrics.latency_ms_record(intent_type="flywheel", value_ms=200)
    metrics.latency_ms_record(intent_type="flywheel", value_ms=300)

    snapshot = metrics.snapshot()
    assert snapshot["interpret.latency_ms"]["flywheel"]["count"] == 3
    assert snapshot["interpret.latency_ms"]["flywheel"]["sum"] == 600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_observability.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement structured logging**

Create `apps/backend/services/interpreter/observability/logging.py`:
```python
"""Structured logging with structlog, JSON output for Cloud Logging."""
from __future__ import annotations

import hashlib
import logging
import sys
from typing import Any

import structlog


def configure_logging(
    *, level: str = "INFO", json_output: bool = True
) -> None:
    """Configure structlog and stdlib logging. Call once at startup."""
    logging.basicConfig(
        level=level.upper(),
        stream=sys.stdout,
        format="%(message)s",
    )
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named bound logger."""
    return structlog.get_logger(name)


def hash_prompt(prompt: str) -> str:
    """Return a stable sha256 hex hash of `prompt` for PII-safe logging."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Implement in-process metrics**

Create `apps/backend/services/interpreter/observability/metrics.py`:
```python
"""Lightweight in-process metrics. Flushed to Cloud Monitoring by an exporter."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class _Histogram:
    count: int = 0
    sum: float = 0.0

    def record(self, value: float) -> None:
        self.count += 1
        self.sum += value


@dataclass
class InterpreterMetrics:
    """In-process counters and histograms. Thread-safe."""

    _lock: Lock = field(default_factory=Lock)
    _counters: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    _histograms: dict[str, dict[str, _Histogram]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(_Histogram))
    )
    _gauges: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def request_count_inc(
        self, *, status: str, language: str, intent_type: str
    ) -> None:
        key = f"{status}|{language}|{intent_type}"
        with self._lock:
            self._counters["interpret.request_count"][key] += 1

    def retry_count_inc(self, *, error_code: str) -> None:
        with self._lock:
            self._counters["interpret.retry_count"][error_code] += 1

    def latency_ms_record(self, *, intent_type: str, value_ms: float) -> None:
        with self._lock:
            self._histograms["interpret.latency_ms"][intent_type].record(value_ms)

    def gemma_tokens_inc(self, *, direction: str, count: int) -> None:
        with self._lock:
            self._counters["interpret.gemma_tokens_total"][direction] += count

    def degraded_mode_set(self, *, active: bool) -> None:
        with self._lock:
            self._gauges["interpret.degraded_mode_active"] = 1.0 if active else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **{k: dict(v) for k, v in self._counters.items()},
                **{
                    k: {kk: {"count": vv.count, "sum": vv.sum}
                        for kk, vv in v.items()}
                    for k, v in self._histograms.items()
                },
                **{k: float(v) for k, v in self._gauges.items()},
            }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/unit/test_observability.py -v`
Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/interpreter/observability/ \
  apps/backend/tests/unit/test_observability.py
git commit -m "feat(interpreter): add structlog-based logging and in-process metrics"
```

---

## Task 13: Prompt loader

**Files:**
- Create: `apps/backend/prompts/interpreter_system.md`
- Create: `apps/backend/services/interpreter/agent/__init__.py`
- Create: `apps/backend/services/interpreter/agent/prompt_loader.py`
- Test: `apps/backend/tests/unit/test_prompt_loader.py`

- [ ] **Step 1: Create system prompt**

Create `apps/backend/prompts/interpreter_system.md`:
```markdown
# Interpreter System Prompt

## Role

You are an expert mechanical engineering assistant. You help non-engineers design mechanical components by extracting structured specifications from their natural-language descriptions.

You prioritize CLARITY, SAFETY, and COMPOSABILITY.

## Tools Protocol

You have access to exactly 4 tools:

1. `list_primitives()` — discovers the primitive components you can build with.
2. `get_primitive_schema(name)` — retrieves the parameter schema for a specific primitive.
3. `search_materials(criteria)` — filters the materials catalog by category, density, strength, or sustainability.
4. `get_material_properties(name)` — returns full properties of a specific material.

### Rules

- You MUST call `list_primitives()` FIRST before naming any primitive.
- NEVER invent primitive names. Use only names returned by `list_primitives()`.
- When the user mentions exotic or sustainable materials, use `search_materials()` to find suitable ones.
- For common materials (steel, aluminum, plastic), you may reference them directly but call `get_material_properties()` to confirm the exact grade.

## Output Contract

Your final response MUST be a JSON object matching this shape:

```json
{
  "type": "<primitive_name>",
  "fields": {
    "<field_name>": {
      "value": <value_or_null>,
      "source": "extracted" | "defaulted" | "missing",
      "reason": "<required if source is 'defaulted'>",
      "required": true|false,
      "original": "<optional: user's original unit expression>"
    }
  },
  "composed_of": ["<additional_primitive_names>"]
}
```

### Tri-state source field

- `extracted`: the user explicitly stated this value.
- `defaulted`: you inferred a reasonable default. Include `reason` explaining why.
- `missing`: the user did not specify this and you cannot infer it. Set `value` to `null` and `required` to `true`.

## Language

- Detect the language of the user's input ("es" or "en").
- Respond in the SAME language for any prose fields.
- JSON keys (field names, source values) remain in English.

## Units

- Parse any unit the user provides (metric or imperial).
- Do NOT convert — include the raw expression in `original`. The server will normalize to SI.
- If units are missing, do not assume a default — mark as missing or ask.

## Few-shot examples

### Example 1 (ES)

User: "Necesito un volante de inercia de 500 kg a 3000 RPM"

Expected output (after tool calls):
```json
{
  "type": "Flywheel_Rim",
  "fields": {
    "rpm": {"value": "3000 rpm", "source": "extracted", "original": "3000 RPM"},
    "outer_diameter_m": {"value": null, "source": "missing", "required": true},
    "inner_diameter_m": {"value": null, "source": "missing", "required": true},
    "thickness_m": {"value": null, "source": "missing", "required": true}
  },
  "composed_of": []
}
```

### Example 2 (EN)

User: "Design a hydroelectric generator for 5 m³/s flow at 20m head"

Expected output (after tool calls):
```json
{
  "type": "Pelton_Runner",
  "fields": {
    "runner_diameter_m": {
      "value": 0.8,
      "source": "defaulted",
      "reason": "calculated from head using D = 38√H / N",
      "required": true
    },
    "bucket_count": {
      "value": 20,
      "source": "defaulted",
      "reason": "standard Pelton recommendation for this diameter",
      "required": true
    }
  },
  "composed_of": ["Shaft", "Housing", "Mounting_Frame"]
}
```
```

- [ ] **Step 2: Write failing test**

Create `apps/backend/tests/unit/test_prompt_loader.py`:
```python
"""Unit tests for the prompt loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.agent.prompt_loader import load_system_prompt


def test_load_system_prompt_returns_full_text() -> None:
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    prompt = load_system_prompt(prompts_dir)
    assert "Role" in prompt
    assert "Tools Protocol" in prompt
    assert "Output Contract" in prompt
    assert "tri-state" in prompt.lower()
    assert "list_primitives" in prompt
    assert len(prompt) > 500


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_system_prompt(tmp_path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_prompt_loader.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 4: Implement prompt loader**

Create `apps/backend/services/interpreter/agent/__init__.py` (empty).

Create `apps/backend/services/interpreter/agent/prompt_loader.py`:
```python
"""Load prompts from disk. Prompts MUST live in markdown files, never in code."""
from __future__ import annotations

from pathlib import Path


SYSTEM_PROMPT_FILENAME = "interpreter_system.md"


def load_system_prompt(prompts_dir: Path) -> str:
    """Return the contents of the interpreter system prompt markdown file.

    Raises FileNotFoundError if the prompt file is missing.
    """
    path = prompts_dir / SYSTEM_PROMPT_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"System prompt not found at {path}. Did you create prompts/interpreter_system.md?"
        )
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_prompt_loader.py -v`
Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/prompts/interpreter_system.md \
  apps/backend/services/interpreter/agent/ \
  apps/backend/tests/unit/test_prompt_loader.py
git commit -m "feat(interpreter): add system prompt and loader"
```

---

## Task 14: Retry policy

**Files:**
- Create: `apps/backend/services/interpreter/agent/retry_policy.py`
- Test: `apps/backend/tests/unit/test_retry_policy.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_retry_policy.py`:
```python
"""Unit tests for retry policy."""
from __future__ import annotations

from services.interpreter.agent.retry_policy import (
    RetryDecision,
    RetryStrategy,
    decide,
)
from services.interpreter.domain.errors import ErrorCode


def test_invalid_json_retries_once_with_corrective_prompt() -> None:
    d = decide(error_code=ErrorCode.INVALID_JSON_RETRY_FAILED, attempt=0)
    assert d == RetryDecision(
        should_retry=True, strategy=RetryStrategy.CORRECTIVE_PROMPT, backoff_s=0.0
    )


def test_invalid_json_does_not_retry_twice() -> None:
    d = decide(error_code=ErrorCode.INVALID_JSON_RETRY_FAILED, attempt=1)
    assert d.should_retry is False


def test_vertex_rate_limit_uses_exponential_backoff() -> None:
    d = decide(error_code=ErrorCode.VERTEX_AI_RATE_LIMIT, attempt=0)
    assert d.should_retry is True
    assert d.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    assert d.backoff_s > 0.0


def test_vertex_timeout_does_not_retry() -> None:
    d = decide(error_code=ErrorCode.VERTEX_AI_TIMEOUT, attempt=0)
    assert d.should_retry is False
    assert d.strategy == RetryStrategy.FAIL_FAST


def test_physical_range_does_not_retry_returns_to_user() -> None:
    d = decide(error_code=ErrorCode.PHYSICAL_RANGE_VIOLATION, attempt=0)
    assert d.should_retry is False
    assert d.strategy == RetryStrategy.RETURN_TO_USER


def test_unknown_primitive_retries_once_with_corrective() -> None:
    d = decide(error_code=ErrorCode.UNKNOWN_PRIMITIVE, attempt=0)
    assert d.should_retry is True
    assert d.strategy == RetryStrategy.CORRECTIVE_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_retry_policy.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement retry policy**

Create `apps/backend/services/interpreter/agent/retry_policy.py`:
```python
"""Per-error retry policy. Max 1 retry per error type."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from services.interpreter.domain.errors import ErrorCode


class RetryStrategy(StrEnum):
    CORRECTIVE_PROMPT = "corrective_prompt"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FAIL_FAST = "fail_fast"
    RETURN_TO_USER = "return_to_user"


class RetryDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    should_retry: bool
    strategy: RetryStrategy
    backoff_s: float = 0.0


_POLICY: dict[ErrorCode, tuple[int, RetryStrategy]] = {
    ErrorCode.INVALID_JSON_RETRY_FAILED: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.UNKNOWN_PRIMITIVE: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.VERTEX_AI_TIMEOUT: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.VERTEX_AI_RATE_LIMIT: (1, RetryStrategy.EXPONENTIAL_BACKOFF),
    ErrorCode.PHYSICAL_RANGE_VIOLATION: (0, RetryStrategy.RETURN_TO_USER),
    ErrorCode.AMBIGUOUS_INTENT: (1, RetryStrategy.CORRECTIVE_PROMPT),
    ErrorCode.UNIT_PARSE_FAILED: (0, RetryStrategy.RETURN_TO_USER),
    ErrorCode.SESSION_NOT_FOUND: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.SESSION_EXPIRED: (0, RetryStrategy.FAIL_FAST),
    ErrorCode.INTERNAL_ERROR: (0, RetryStrategy.FAIL_FAST),
}


def decide(*, error_code: ErrorCode, attempt: int) -> RetryDecision:
    """Return whether to retry given the error and attempt number (0-indexed)."""
    max_retries, strategy = _POLICY.get(
        error_code, (0, RetryStrategy.FAIL_FAST)
    )
    if attempt >= max_retries:
        return RetryDecision(should_retry=False, strategy=strategy)
    backoff = 0.0
    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        backoff = 2.0 ** attempt  # 1.0s, 2.0s, ...
    return RetryDecision(
        should_retry=True, strategy=strategy, backoff_s=backoff
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_retry_policy.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/services/interpreter/agent/retry_policy.py \
  apps/backend/tests/unit/test_retry_policy.py
git commit -m "feat(interpreter): add retry policy with max 1 retry per error code"
```

---

## Task 15: Agent orchestrator (with Gemma protocol abstraction)

**Files:**
- Create: `apps/backend/services/interpreter/agent/orchestrator.py`
- Create: `apps/backend/services/interpreter/agent/gemma_client.py`
- Test: `apps/backend/tests/component/test_agent_loop.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/component/test_agent_loop.py`:
```python
"""Component tests for the agent orchestrator (with mocked Gemma)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
    GemmaToolCall,
)
from services.interpreter.agent.orchestrator import (
    Orchestrator,
    OrchestratorOutput,
)
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry


BACKEND_ROOT = Path(__file__).parent.parent.parent


class _ScriptedGemma(GemmaProtocol):
    """A Gemma stub that replays a predetermined sequence of events."""

    def __init__(self, scripts: list[list[GemmaEvent]]) -> None:
        self._scripts = scripts
        self._call = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        script = self._scripts[self._call]
        self._call += 1
        for event in script:
            yield event


@pytest.fixture
def tool_registry() -> ToolRegistry:
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    return ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )


@pytest.fixture
def system_prompt() -> str:
    return load_system_prompt(BACKEND_ROOT / "prompts")


async def test_agent_calls_list_primitives_first(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(name="list_primitives", args={})),
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(
                               name="get_primitive_schema",
                               args={"name": "Shaft"})),
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": 0.05, "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                ),
            ]
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a 5cm shaft 50cm long")
    assert isinstance(output, OrchestratorOutput)
    assert output.intent.type == "Shaft"
    tool_names = [e.tool_call.name for e in output.events if e.kind == "tool_call"]
    assert tool_names[0] == "list_primitives"


async def test_agent_handles_unknown_primitive_with_retry(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "SuperFlywheel",
                        "fields": {},
                        "composed_of": [],
                    },
                ),
            ],
            [
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Flywheel_Rim",
                        "fields": {
                            "outer_diameter_m": {"value": 0.5, "source": "extracted"},
                            "inner_diameter_m": {"value": 0.1, "source": "extracted"},
                            "thickness_m": {"value": 0.05, "source": "extracted"},
                            "rpm": {"value": 3000, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                ),
            ],
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a flywheel")
    assert output.intent.type == "Flywheel_Rim"
    assert output.retry_count == 1


async def test_agent_stops_after_max_retries(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    bad = GemmaEvent(
        kind="final_json",
        final_json={"type": "StillInvented", "fields": {}, "composed_of": []},
    )
    gemma = _ScriptedGemma(scripts=[[bad], [bad]])  # both attempts fail
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    with pytest.raises(Exception):
        await orch.run(user_prompt="invent something")


async def test_agent_invokes_real_tool_dispatch(
    tool_registry: ToolRegistry, system_prompt: str
) -> None:
    gemma = _ScriptedGemma(
        scripts=[
            [
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(name="list_primitives", args={})),
                GemmaEvent(kind="tool_call",
                           tool_call=GemmaToolCall(
                               name="search_materials",
                               args={"criteria": {"category": "metal"}})),
                GemmaEvent(
                    kind="final_json",
                    final_json={
                        "type": "Shaft",
                        "fields": {
                            "diameter_m": {"value": 0.05, "source": "extracted"},
                            "length_m": {"value": 0.5, "source": "extracted"},
                        },
                        "composed_of": [],
                    },
                ),
            ]
        ]
    )
    orch = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )
    output = await orch.run(user_prompt="a shaft in metal")
    # Tool results should have been captured in events.
    tool_events = [e for e in output.events if e.kind == "tool_result"]
    assert any(e.tool_call.name == "search_materials" for e in tool_events)
    # The tool actually executed and returned metals.
    metal_result = next(
        e.tool_result for e in tool_events if e.tool_call.name == "search_materials"
    )
    assert any(m["category"] == "metal" for m in metal_result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/component/test_agent_loop.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement Gemma protocol abstraction**

Create `apps/backend/services/interpreter/agent/gemma_client.py`:
```python
"""Abstraction over Gemma 4 / Vertex AI.

The Protocol allows substituting a scripted stub in tests without
touching the real Vertex AI SDK.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict


class GemmaToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    args: dict[str, Any]


class GemmaEvent(BaseModel):
    """An event emitted by Gemma during generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: Literal["thinking", "tool_call", "tool_result", "final_json", "error"]
    thinking_text: str | None = None
    tool_call: GemmaToolCall | None = None
    tool_result: Any | None = None
    final_json: dict[str, Any] | None = None
    error_message: str | None = None


class GemmaProtocol(Protocol):
    """Abstract Gemma generation API. Real impl uses google-cloud-aiplatform."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        ...
```

- [ ] **Step 4: Implement orchestrator**

Create `apps/backend/services/interpreter/agent/orchestrator.py`:
```python
"""Agent orchestrator: runs Gemma, handles tool calls, applies retry policy."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict

from services.interpreter.agent.gemma_client import GemmaEvent, GemmaProtocol
from services.interpreter.agent.retry_policy import (
    RetryStrategy,
    decide,
)
from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
    InterpreterException,
)
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.primitives_registry import (
    PrimitivesRegistry,
)
from services.interpreter.tools.registry import ToolRegistry


class OrchestratorOutput(BaseModel):
    """Full output of an orchestrator run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    intent: DesignIntent
    events: list[GemmaEvent]
    retry_count: int


_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_primitives",
        "description": "List all registered primitives.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_primitive_schema",
        "description": "Get the full parameter schema of a primitive by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "search_materials",
        "description": "Filter the materials catalog by criteria.",
        "parameters": {
            "type": "object",
            "properties": {"criteria": {"type": "object"}},
            "required": ["criteria"],
        },
    },
    {
        "name": "get_material_properties",
        "description": "Get full properties of a material by name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]


class Orchestrator:
    """Coordinates Gemma generation, tool dispatch, and retries."""

    def __init__(
        self,
        *,
        gemma: GemmaProtocol,
        tools: ToolRegistry,
        system_prompt: str,
        registry: PrimitivesRegistry | None = None,
    ) -> None:
        self._gemma = gemma
        self._tools = tools
        self._system_prompt = system_prompt
        self._registry = registry

    async def run(self, *, user_prompt: str) -> OrchestratorOutput:
        """Execute the agent loop until a valid final_json is produced.

        Retries once per recoverable error (per retry_policy).
        """
        events: list[GemmaEvent] = []
        last_error: InterpreterError | None = None
        retry_count = 0
        for attempt in range(2):  # 1 initial + up to 1 retry
            attempt_events, final_json, error = await self._single_attempt(
                user_prompt=user_prompt,
                corrective_context=(
                    self._corrective_message(last_error) if last_error else None
                ),
            )
            events.extend(attempt_events)
            if error is None and final_json is not None:
                intent = self._build_intent(final_json)
                return OrchestratorOutput(
                    intent=intent, events=events, retry_count=retry_count
                )
            last_error = error
            decision = decide(
                error_code=error.code
                if error
                else ErrorCode.INTERNAL_ERROR,
                attempt=attempt,
            )
            if not decision.should_retry:
                break
            retry_count += 1
            if decision.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                await asyncio.sleep(decision.backoff_s)

        if last_error is None:
            last_error = InterpreterError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Orchestrator exited without producing an intent.",
            )
        raise InterpreterException(last_error)

    async def _single_attempt(
        self, *, user_prompt: str, corrective_context: str | None
    ) -> tuple[list[GemmaEvent], dict | None, InterpreterError | None]:
        collected: list[GemmaEvent] = []
        system = self._system_prompt
        if corrective_context:
            system = f"{system}\n\n## Correction\n{corrective_context}"

        final_json: dict | None = None
        async for ev in self._gemma.generate(
            system_prompt=system,
            user_prompt=user_prompt,
            tools=_TOOL_SCHEMAS,
        ):
            collected.append(ev)
            if ev.kind == "tool_call" and ev.tool_call is not None:
                try:
                    result = self._tools.invoke(
                        ev.tool_call.name, ev.tool_call.args
                    )
                except KeyError as e:
                    return collected, None, InterpreterError(
                        code=ErrorCode.UNKNOWN_PRIMITIVE,
                        message=str(e),
                    )
                collected.append(
                    GemmaEvent(
                        kind="tool_result",
                        tool_call=ev.tool_call,
                        tool_result=result,
                    )
                )
            elif ev.kind == "final_json":
                final_json = ev.final_json
            elif ev.kind == "error":
                return collected, None, InterpreterError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=ev.error_message or "gemma error",
                )

        if final_json is None:
            return collected, None, InterpreterError(
                code=ErrorCode.INVALID_JSON_RETRY_FAILED,
                message="Gemma ended without a final_json event.",
            )

        # Validate referenced primitive is known.
        if self._registry is not None:
            try:
                self._registry.get(final_json.get("type", ""))
            except KeyError:
                return collected, None, InterpreterError(
                    code=ErrorCode.UNKNOWN_PRIMITIVE,
                    message=f"Primitive '{final_json.get('type')}' does not exist.",
                )
        return collected, final_json, None

    def _build_intent(self, final_json: dict) -> DesignIntent:
        return DesignIntent.model_validate(final_json)

    def _corrective_message(self, error: InterpreterError) -> str:
        if error.code == ErrorCode.UNKNOWN_PRIMITIVE:
            return (
                "Your previous response referenced a primitive that does not exist. "
                "Call list_primitives() first and use only names it returns."
            )
        if error.code == ErrorCode.INVALID_JSON_RETRY_FAILED:
            return (
                "Your previous response was not valid JSON. "
                "Return ONLY a valid JSON object matching the Output Contract."
            )
        return "Please retry producing a valid DesignIntent."
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/component/test_agent_loop.py -v`
Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/interpreter/agent/orchestrator.py \
  apps/backend/services/interpreter/agent/gemma_client.py \
  apps/backend/tests/component/test_agent_loop.py
git commit -m "feat(interpreter): add agent orchestrator with retry and tool dispatch"
```

---

## Task 16: API DTOs and SSE serializer

**Files:**
- Create: `apps/backend/services/interpreter/api/__init__.py`
- Create: `apps/backend/services/interpreter/api/dto.py`
- Create: `apps/backend/services/interpreter/api/streaming.py`
- Test: `apps/backend/tests/unit/test_streaming.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_streaming.py`:
```python
"""Unit tests for SSE event serialization."""
from __future__ import annotations

from services.interpreter.api.streaming import (
    SSEEvent,
    serialize_sse,
)


def test_serialize_thinking_event() -> None:
    text = serialize_sse(SSEEvent(event="thinking", data={"message": "hi"}))
    assert text == 'event: thinking\ndata: {"message":"hi"}\n\n'


def test_serialize_tool_call_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="tool_call",
            data={"tool": "list_primitives", "reason": "discover"},
        )
    )
    assert "event: tool_call" in text
    assert '"tool":"list_primitives"' in text


def test_serialize_final_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="final",
            data={
                "session_id": "abc",
                "intent": {"type": "Shaft"},
                "language": "en",
            },
        )
    )
    assert "event: final" in text
    assert '"session_id":"abc"' in text


def test_serialize_error_event() -> None:
    text = serialize_sse(
        SSEEvent(
            event="error",
            data={"code": "vertex_ai_timeout", "message": "timeout"},
        )
    )
    assert "event: error" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_streaming.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement DTOs**

Create `apps/backend/services/interpreter/api/__init__.py` (empty).

Create `apps/backend/services/interpreter/api/dto.py`:
```python
"""HTTP request/response DTOs for the Interpreter API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.interpreter.domain.intent import DesignIntent


class InterpretRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class RefineRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    field_updates: dict[str, Any]


class InterpretResponse(BaseModel):
    """Body of the `final` SSE event and the GET /sessions response."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    intent: DesignIntent
    language: str  # "es" | "en"
```

- [ ] **Step 4: Implement SSE serializer**

Create `apps/backend/services/interpreter/api/streaming.py`:
```python
"""Server-Sent Events serialization for the Interpreter streaming endpoint."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


SSEEventName = Literal[
    "thinking", "tool_call", "tool_result", "partial_intent", "final", "error"
]


class SSEEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: SSEEventName
    data: dict[str, Any]


def serialize_sse(event: SSEEvent) -> str:
    """Serialize an event per the SSE wire format.

    Output: "event: <name>\\ndata: <json>\\n\\n"
    """
    data_json = json.dumps(event.data, separators=(",", ":"))
    return f"event: {event.event}\ndata: {data_json}\n\n"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/unit/test_streaming.py -v`
Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/interpreter/api/ \
  apps/backend/tests/unit/test_streaming.py
git commit -m "feat(interpreter): add API DTOs and SSE serializer"
```

---

## Task 17: POST /interpret streaming endpoint

**Files:**
- Create: `apps/backend/services/interpreter/api/router.py`
- Create: `apps/backend/services/interpreter/app.py`
- Test: `apps/backend/tests/component/test_router_interpret.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/component/test_router_interpret.py`:
```python
"""Component tests for POST /interpret streaming endpoint."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
    GemmaToolCall,
)
from services.interpreter.app import create_app
from services.interpreter.session.fake_store import FakeSessionStore


BACKEND_ROOT = Path(__file__).parent.parent.parent


class _StubGemma(GemmaProtocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        yield GemmaEvent(
            kind="tool_call",
            tool_call=GemmaToolCall(name="list_primitives", args={}),
        )
        yield GemmaEvent(
            kind="final_json",
            final_json={
                "type": "Shaft",
                "fields": {
                    "diameter_m": {"value": 0.05, "source": "extracted"},
                    "length_m": {"value": 0.5, "source": "extracted"},
                },
                "composed_of": [],
            },
        )


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_StubGemma(),
        session_store=FakeSessionStore(),
    )
    return TestClient(app)


def test_interpret_returns_sse_stream(client: TestClient) -> None:
    with client.stream(
        "POST",
        "/interpret",
        json={"prompt": "a 5cm shaft 50cm long"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")
        assert "event: tool_call" in body
        assert "event: final" in body
        assert '"type":"Shaft"' in body


def test_interpret_validation_error_on_empty_prompt(client: TestClient) -> None:
    response = client.post("/interpret", json={"prompt": ""})
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/component/test_router_interpret.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement router**

Create `apps/backend/services/interpreter/api/router.py`:
```python
"""FastAPI router for the Interpreter endpoints."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.agent.gemma_client import GemmaEvent
from services.interpreter.api.dto import (
    InterpretRequest,
    InterpretResponse,
    RefineRequest,
)
from services.interpreter.api.streaming import SSEEvent, serialize_sse
from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterException,
)
from services.interpreter.domain.validators import validate_physical_consistency
from services.interpreter.session.merge import merge_refinement
from services.interpreter.session.store import Session, SessionMessage


router = APIRouter()


def _detect_language(text: str) -> Literal["es", "en"]:
    # Minimal heuristic; replaced by Gemma-reported language post-generation.
    es_markers = {"diseña", "necesito", "un ", "una ", "con ", "para "}
    lower = text.lower()
    return "es" if any(m in lower for m in es_markers) else "en"


@router.post("/interpret")
async def interpret(req: InterpretRequest, request: Request) -> StreamingResponse:
    orchestrator: Orchestrator = request.app.state.orchestrator
    store = request.app.state.session_store
    registry = request.app.state.registry

    language = _detect_language(req.prompt)

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            session: Session
            if req.session_id:
                session = await store.load(req.session_id)
            else:
                session = await store.create_session(
                    user_id="anonymous", language=language
                )

            await store.append_message(
                session.session_id,
                SessionMessage(
                    role="user", content=req.prompt, timestamp=datetime.now(UTC)
                ),
            )

            yield serialize_sse(
                SSEEvent(event="thinking", data={"message": "Analyzing your design..."})
            ).encode("utf-8")

            output = await orchestrator.run(user_prompt=req.prompt)

            for ev in output.events:
                if ev.kind == "tool_call" and ev.tool_call is not None:
                    yield serialize_sse(
                        SSEEvent(
                            event="tool_call",
                            data={
                                "tool": ev.tool_call.name,
                                "args": ev.tool_call.args,
                            },
                        )
                    ).encode("utf-8")
                elif ev.kind == "tool_result":
                    continue  # internal; not surfaced to the client

            validate_physical_consistency(output.intent, registry)
            await store.update_intent(
                session.session_id, output.intent, user_overrides={}
            )

            yield serialize_sse(
                SSEEvent(
                    event="final",
                    data=InterpretResponse(
                        session_id=session.session_id,
                        intent=output.intent,
                        language=language,
                    ).model_dump(mode="json"),
                )
            ).encode("utf-8")
        except InterpreterException as e:
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data=e.error.model_dump(mode="json"),
                )
            ).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/interpret/refine", response_model=InterpretResponse)
async def interpret_refine(
    req: RefineRequest, request: Request
) -> InterpretResponse:
    store = request.app.state.session_store
    registry = request.app.state.registry

    session = await store.load(req.session_id)
    if session.current_intent is None:
        raise HTTPException(status_code=404, detail="No intent for this session yet.")

    updated = merge_refinement(session.current_intent, req.field_updates)
    try:
        validate_physical_consistency(updated, registry)
    except InterpreterException as e:
        if e.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION:
            raise HTTPException(
                status_code=422,
                detail={
                    "errors": [e.error.model_dump(mode="json")],
                },
            ) from e
        raise

    await store.update_intent(
        req.session_id, updated, user_overrides=session.user_overrides
    )
    return InterpretResponse(
        session_id=req.session_id,
        intent=updated,
        language=session.language,
    )


@router.get("/interpret/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    store = request.app.state.session_store
    session = await store.load(session_id)
    return {"session": session.model_dump(mode="json")}
```

- [ ] **Step 4: Implement app factory**

Create `apps/backend/services/interpreter/app.py`:
```python
"""FastAPI application factory for the Interpreter service."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.interpreter.agent.gemma_client import GemmaProtocol
from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.api.router import router as interpret_router
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.session.store import SessionStore
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry


def create_app(
    *,
    prompts_dir: Path,
    materials_path: Path,
    gemma: GemmaProtocol,
    session_store: SessionStore,
    cors_allowed_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="S1 Interpreter", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    catalog = load_catalog(materials_path)
    tool_registry = ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )
    system_prompt = load_system_prompt(prompts_dir)

    orchestrator = Orchestrator(
        gemma=gemma,
        tools=tool_registry,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )

    app.state.orchestrator = orchestrator
    app.state.session_store = session_store
    app.state.registry = DEFAULT_REGISTRY
    app.state.catalog = catalog

    app.include_router(interpret_router)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/component/test_router_interpret.py -v`
Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add apps/backend/services/interpreter/api/router.py \
  apps/backend/services/interpreter/app.py \
  apps/backend/tests/component/test_router_interpret.py
git commit -m "feat(interpreter): add POST /interpret SSE endpoint and app factory"
```

---

## Task 18: POST /refine and GET /sessions endpoints

**Files:**
- Test: `apps/backend/tests/component/test_router_refine.py`

Endpoints already added in Task 17 — this task adds component tests to validate them end-to-end.

- [ ] **Step 1: Write component tests**

Create `apps/backend/tests/component/test_router_refine.py`:
```python
"""Component tests for /interpret/refine and GET /sessions."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaProtocol,
)
from services.interpreter.app import create_app
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.fake_store import FakeSessionStore


BACKEND_ROOT = Path(__file__).parent.parent.parent


class _NullGemma(GemmaProtocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        # not used in these tests
        if False:
            yield GemmaEvent(kind="error", error_message="unused")


@pytest.fixture
def client_and_store() -> tuple[TestClient, FakeSessionStore]:
    store = FakeSessionStore()
    app = create_app(
        prompts_dir=BACKEND_ROOT / "prompts",
        materials_path=BACKEND_ROOT / "data" / "materials.json",
        gemma=_NullGemma(),
        session_store=store,
    )
    return TestClient(app), store


async def _seed_session_with_intent(store: FakeSessionStore) -> str:
    session = await store.create_session(user_id="u1", language="en")
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
            "length_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
        },
    )
    await store.update_intent(session.session_id, intent, user_overrides={})
    return session.session_id


async def test_refine_applies_field_updates(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    response = client.post(
        "/interpret/refine",
        json={"session_id": session_id, "field_updates": {"diameter_m": 0.08}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"]["fields"]["diameter_m"]["value"] == 0.08
    assert body["intent"]["fields"]["diameter_m"]["source"] == "user"


async def test_refine_returns_422_on_invalid_range(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    # diameter max is 1.0m; 2.0 is out of range.
    response = client.post(
        "/interpret/refine",
        json={"session_id": session_id, "field_updates": {"diameter_m": 2.0}},
    )
    assert response.status_code == 422


async def test_refine_returns_404_on_unknown_session(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, _ = client_and_store
    response = client.post(
        "/interpret/refine",
        json={"session_id": "nonexistent", "field_updates": {}},
    )
    assert response.status_code == 404


async def test_get_session_returns_state(
    client_and_store: tuple[TestClient, FakeSessionStore],
) -> None:
    client, store = client_and_store
    session_id = await _seed_session_with_intent(store)

    response = client.get(f"/interpret/sessions/{session_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["session"]["session_id"] == session_id
    assert body["session"]["current_intent"]["type"] == "Shaft"
```

- [ ] **Step 2: Run tests**

Run: `cd apps/backend && uv run pytest tests/component/test_router_refine.py -v`
Expected: 4 PASSED.

- [ ] **Step 3: Commit**

```bash
git add apps/backend/tests/component/test_router_refine.py
git commit -m "test(interpreter): add component tests for /refine and /sessions"
```

---

## Task 19: Degraded mode circuit breaker

**Files:**
- Create: `apps/backend/services/interpreter/agent/circuit_breaker.py`
- Test: `apps/backend/tests/unit/test_circuit_breaker.py`

- [ ] **Step 1: Write failing test**

Create `apps/backend/tests/unit/test_circuit_breaker.py`:
```python
"""Unit tests for the degraded-mode circuit breaker."""
from __future__ import annotations

import time

from services.interpreter.agent.circuit_breaker import DegradedModeBreaker


def test_closed_initially() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    assert b.is_open() is False


def test_opens_after_threshold_failures() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    assert b.is_open() is False
    b.record_failure()
    assert b.is_open() is True


def test_success_resets_failures() -> None:
    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    b.record_success()
    b.record_failure()
    assert b.is_open() is False  # counter reset between failures


def test_closes_automatically_after_duration(monkeypatch) -> None:
    current = [1_000_000.0]

    def fake_monotonic() -> float:
        return current[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    b = DegradedModeBreaker(failure_threshold=2, duration_seconds=60)
    b.record_failure()
    b.record_failure()
    assert b.is_open() is True

    current[0] += 61.0
    assert b.is_open() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/unit/test_circuit_breaker.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement circuit breaker**

Create `apps/backend/services/interpreter/agent/circuit_breaker.py`:
```python
"""Simple time-window circuit breaker for Vertex AI degraded mode."""
from __future__ import annotations

import time
from threading import Lock


class DegradedModeBreaker:
    """Opens after N consecutive failures, closes after a fixed duration.

    Uses time.monotonic so tests can monkeypatch it deterministically.
    """

    def __init__(self, *, failure_threshold: int, duration_seconds: int) -> None:
        self._threshold = failure_threshold
        self._duration = duration_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = time.monotonic()

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._duration:
                self._opened_at = None
                self._failures = 0
                return False
            return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/unit/test_circuit_breaker.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Wire breaker into router**

Edit `apps/backend/services/interpreter/api/router.py` — add at the top of the `event_stream` function inside `interpret`:
```python
        # Degraded mode check
        breaker = request.app.state.breaker
        if breaker.is_open():
            yield serialize_sse(
                SSEEvent(
                    event="error",
                    data={
                        "code": "vertex_ai_rate_limit",
                        "message": (
                            "AI assistant temporarily unavailable. "
                            "Please use manual mode or retry in 60 seconds."
                        ),
                        "retry_after": 60,
                    },
                )
            ).encode("utf-8")
            return
```

Edit `apps/backend/services/interpreter/app.py` — in `create_app`, after `app.state.catalog = catalog`:
```python
    from services.interpreter.agent.circuit_breaker import DegradedModeBreaker

    app.state.breaker = DegradedModeBreaker(
        failure_threshold=2, duration_seconds=60
    )
```

Also wrap orchestrator run with breaker tracking in router — in `interpret()` event_stream, wrap:
```python
        try:
            output = await orchestrator.run(user_prompt=req.prompt)
            breaker.record_success()
        except InterpreterException as e:
            if e.error.code in ("vertex_ai_timeout", "vertex_ai_rate_limit", "internal_error"):
                breaker.record_failure()
            raise
```

- [ ] **Step 6: Run full test suite to ensure nothing broke**

Run: `cd apps/backend && uv run pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/services/interpreter/agent/circuit_breaker.py \
  apps/backend/services/interpreter/api/router.py \
  apps/backend/services/interpreter/app.py \
  apps/backend/tests/unit/test_circuit_breaker.py
git commit -m "feat(interpreter): add degraded-mode circuit breaker"
```

---

## Task 20: Real Gemma client + golden fixture capture

**Files:**
- Create: `apps/backend/services/interpreter/agent/vertex_gemma.py`
- Create: `apps/backend/tests/fixtures/__init__.py`
- Create: `apps/backend/tests/integration/__init__.py`
- Create: `apps/backend/tests/integration/test_vertex_real.py`
- Create: `apps/backend/tests/fixtures/gemma_responses/.gitkeep`

- [ ] **Step 1: Implement real Gemma client**

Create `apps/backend/services/interpreter/agent/vertex_gemma.py`:
```python
"""Real Gemma 4 client using google-cloud-aiplatform Vertex AI SDK."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from google.cloud import aiplatform  # type: ignore[import-untyped]
from vertexai.generative_models import (  # type: ignore[import-untyped]
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

from services.interpreter.agent.gemma_client import (
    GemmaEvent,
    GemmaToolCall,
)


class VertexGemmaClient:
    """Real implementation backed by Vertex AI."""

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        model_name: str,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ) -> None:
        aiplatform.init(project=project_id, location=region)
        self._model = GenerativeModel(model_name)
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        previous_messages: list[dict] | None = None,
    ) -> AsyncIterator[GemmaEvent]:
        declarations = [FunctionDeclaration(**t) for t in tools]
        vertex_tools = [Tool(function_declarations=declarations)]

        response = await self._model.generate_content_async(  # type: ignore[attr-defined]
            [system_prompt, user_prompt],
            tools=vertex_tools,
            generation_config={
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        )

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    yield GemmaEvent(
                        kind="tool_call",
                        tool_call=GemmaToolCall(
                            name=part.function_call.name,
                            args=dict(part.function_call.args),
                        ),
                    )
                elif hasattr(part, "text") and part.text:
                    try:
                        parsed: dict[str, Any] = json.loads(part.text)
                        yield GemmaEvent(kind="final_json", final_json=parsed)
                    except json.JSONDecodeError:
                        yield GemmaEvent(
                            kind="error",
                            error_message=f"Non-JSON final content: {part.text[:100]}",
                        )
```

- [ ] **Step 2: Create integration test**

Create `apps/backend/tests/integration/__init__.py` (empty).
Create `apps/backend/tests/fixtures/__init__.py` (empty).
Create `apps/backend/tests/fixtures/gemma_responses/.gitkeep` (empty).

Create `apps/backend/tests/integration/test_vertex_real.py`:
```python
"""Integration tests hitting real Vertex AI. Requires GCP credentials.

Run with: uv run pytest tests/integration/ -m vertex
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from services.interpreter.agent.orchestrator import Orchestrator
from services.interpreter.agent.prompt_loader import load_system_prompt
from services.interpreter.agent.vertex_gemma import VertexGemmaClient
from services.interpreter.domain.materials import load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import build_materials_tools
from services.interpreter.tools.primitives import build_primitives_tools
from services.interpreter.tools.registry import ToolRegistry


BACKEND_ROOT = Path(__file__).parent.parent.parent


pytestmark = pytest.mark.vertex


@pytest.fixture
def orchestrator() -> Orchestrator:
    project_id = os.environ["GCP_PROJECT_ID"]
    region = os.environ.get("GCP_REGION", "us-central1")
    model_name = os.environ.get("VERTEX_AI_ENDPOINT", "gemma-4-instruct")

    gemma = VertexGemmaClient(
        project_id=project_id,
        region=region,
        model_name=model_name,
    )
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    tools = ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )
    system_prompt = load_system_prompt(BACKEND_ROOT / "prompts")
    return Orchestrator(
        gemma=gemma,
        tools=tools,
        system_prompt=system_prompt,
        registry=DEFAULT_REGISTRY,
    )


async def test_real_flywheel_extraction_es(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Diseña un volante de inercia para 500 kJ a 3000 RPM"
    )
    assert output.intent.type == "Flywheel_Rim"


async def test_real_hydro_extraction_en(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Design a hydroelectric generator for 5 m³/s flow at 20m head"
    )
    assert output.intent.type == "Pelton_Runner"


async def test_real_shelter_extraction_es(orchestrator: Orchestrator) -> None:
    output = await orchestrator.run(
        user_prompt="Un refugio plegable para 4 personas, viento 100 km/h"
    )
    assert output.intent.type == "Hinge_Panel"


async def test_real_bilingual_mixed_units(orchestrator: Orchestrator) -> None:
    # Tests imperial parsing path.
    output = await orchestrator.run(
        user_prompt="A shaft 2 inches in diameter and 18 inches long"
    )
    assert output.intent.type == "Shaft"


async def test_real_missing_field_marked_missing(
    orchestrator: Orchestrator,
) -> None:
    output = await orchestrator.run(user_prompt="a flywheel for my project")
    assert output.intent.has_missing_fields()
```

- [ ] **Step 3: Verify integration tests are skipped without GCP**

Run: `cd apps/backend && uv run pytest tests/integration/ -v`
Expected: 5 DESELECTED (because `-m vertex` not passed) OR 5 ERRORS if env vars missing. That's OK.

Run: `cd apps/backend && uv run pytest -m "not vertex" -v`
Expected: only non-vertex tests run; all PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/services/interpreter/agent/vertex_gemma.py \
  apps/backend/tests/integration/ \
  apps/backend/tests/fixtures/
git commit -m "feat(interpreter): add VertexGemmaClient and integration test suite"
```

---

## Task 21: Dockerfile and deployment script

**Files:**
- Create: `apps/backend/Dockerfile`
- Create: `apps/backend/.dockerignore`
- Create: `apps/backend/main.py`
- Create: `infra/deploy-backend.sh`

- [ ] **Step 1: Create main.py entrypoint**

Create `apps/backend/main.py`:
```python
"""Uvicorn entrypoint for the Interpreter backend."""
from __future__ import annotations

import os
from pathlib import Path

from google.cloud import firestore  # type: ignore[import-untyped]

from services.interpreter.agent.vertex_gemma import VertexGemmaClient
from services.interpreter.app import create_app
from services.interpreter.config import Settings
from services.interpreter.observability.logging import configure_logging
from services.interpreter.session.store import FirestoreSessionStore


settings = Settings()
configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))

BACKEND_ROOT = Path(__file__).parent

gemma = VertexGemmaClient(
    project_id=settings.gcp_project_id,
    region=settings.gcp_region,
    model_name=settings.vertex_ai_endpoint,
    temperature=settings.gemma_temperature,
    max_output_tokens=settings.gemma_max_tokens,
)
store = FirestoreSessionStore(firestore.AsyncClient(project=settings.gcp_project_id))

app = create_app(
    prompts_dir=BACKEND_ROOT / "prompts",
    materials_path=BACKEND_ROOT / "data" / "materials.json",
    gemma=gemma,
    session_store=store,
    cors_allowed_origins=settings.cors_allowed_origins,
)
```

- [ ] **Step 2: Create Dockerfile**

Create `apps/backend/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS builder

RUN pip install --no-cache-dir uv==0.5.0

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --no-dev --frozen || uv sync --no-dev

COPY services ./services
COPY prompts ./prompts
COPY data ./data
COPY main.py ./

FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

- [ ] **Step 3: Create .dockerignore**

Create `apps/backend/.dockerignore`:
```
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
tests/
*.egg-info/
```

- [ ] **Step 4: Create deploy script**

Create `infra/deploy-backend.sh`:
```bash
#!/usr/bin/env bash
# Deploy the Interpreter backend to Cloud Run.
# Usage: ./infra/deploy-backend.sh [cors_origins]
#
# Required environment: GCP_PROJECT_ID, GCP_REGION
set -euo pipefail

: "${GCP_PROJECT_ID:?must be set}"
: "${GCP_REGION:?must be set}"

CORS="${1:-https://mechdesign-ai.vercel.app}"

cd "$(dirname "$0")/../apps/backend"

gcloud run deploy orchestrator \
  --source . \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 60 \
  --set-env-vars "GCP_PROJECT_ID=$GCP_PROJECT_ID,GCP_REGION=$GCP_REGION,VERTEX_AI_ENDPOINT=gemma-4-instruct,CORS_ALLOWED_ORIGINS=$CORS,GCS_BUCKET_ARTIFACTS=mechdesign-artifacts"

echo "Deployed. Health check:"
SERVICE_URL=$(gcloud run services describe orchestrator \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" --format="value(status.url)")
curl -fsSL "$SERVICE_URL/healthz" && echo
```

- [ ] **Step 5: Make deploy script executable**

Run: `chmod +x infra/deploy-backend.sh`

- [ ] **Step 6: Verify Dockerfile builds locally (do NOT push)**

Run: `cd apps/backend && docker build -t interpreter-local .`
Expected: successful build, final image tagged `interpreter-local`.

If docker is unavailable, skip this step — Cloud Build will validate on deploy.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/main.py apps/backend/Dockerfile \
  apps/backend/.dockerignore infra/deploy-backend.sh
git commit -m "build(interpreter): add Dockerfile, main entrypoint, and deploy script"
```

---

## Task 22: Service README

**Files:**
- Create: `apps/backend/services/interpreter/README.md`

- [ ] **Step 1: Write README**

Create `apps/backend/services/interpreter/README.md`:
```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/backend/services/interpreter/README.md
git commit -m "docs(interpreter): add service README with endpoints and runbook"
```

---

## Final verification

- [ ] **Run the full test suite (excluding vertex integration)**

Run: `cd apps/backend && uv run pytest -m "not vertex" --cov=services.interpreter --cov-report=term-missing`
Expected: ALL tests PASS. Coverage ≥85%.

- [ ] **Run the linter**

Run: `cd apps/backend && uv run ruff check services/ tests/`
Expected: no errors.

- [ ] **Type-check**

Run: `cd apps/backend && uv run mypy services/interpreter/`
Expected: success (or fix issues inline).

- [ ] **Final commit with any lint/type fixes**

```bash
git add -u
git commit -m "chore(interpreter): finalize lint and type checks" || echo "nothing to commit"
```

---

## Summary

This plan builds the S1 Interpreter backend subsystem from scratch in 22 TDD tasks. Each task produces committed, tested code. Golden fixtures enable fast dev loops without burning Vertex AI quota.

**Not included in this plan** (separate plans needed):
- Frontend (Next.js / Vercel)
- S2 Geometry, S3 Physics, S4 Explainer, S5 Documenter subsystems
- Infra automation beyond the deploy script
- CI pipelines (GitHub Actions / Cloud Build)
- Frontend ↔ backend contracts package (`packages/contracts/`)
