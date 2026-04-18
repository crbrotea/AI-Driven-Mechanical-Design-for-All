"""Uvicorn entrypoint for the Interpreter backend."""
from __future__ import annotations

import os
from pathlib import Path

from google.cloud import firestore

from services.interpreter.agent.vertex_gemma import VertexGemmaClient
from services.interpreter.app import create_app
from services.interpreter.config import Settings
from services.interpreter.observability.logging import configure_logging
from services.interpreter.session.store import FirestoreSessionStore

settings = Settings()  # type: ignore[call-arg]
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
    degraded_mode_failure_threshold=settings.degraded_mode_failure_threshold,
    degraded_mode_duration_seconds=settings.degraded_mode_duration_seconds,
)

# --- Wire S2 Geometry ---
from services.geometry.api.router import router as geometry_router  # noqa: E402
from services.geometry.cache import GcsGeometryCache  # noqa: E402
from services.geometry.pipeline import GeometryPipeline  # noqa: E402
from google.cloud import storage as gcs_storage  # type: ignore[import-untyped]  # noqa: E402

_gcs_client = gcs_storage.Client(project=settings.gcp_project_id)
_geometry_cache = GcsGeometryCache(
    gcs_client=_gcs_client,
    bucket_name=settings.gcs_bucket_artifacts,
    ttl_hours=settings.signed_url_ttl_hours,
)
_materials_catalog = app.state.catalog  # reuse S1's loaded catalog
_geometry_pipeline = GeometryPipeline(
    cache=_geometry_cache,
    materials_catalog=_materials_catalog,
)
app.state.geometry_pipeline = _geometry_pipeline
app.state.geometry_cache = _geometry_cache
app.include_router(geometry_router)
