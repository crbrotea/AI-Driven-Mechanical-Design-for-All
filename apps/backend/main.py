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
