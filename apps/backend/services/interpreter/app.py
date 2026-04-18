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

    from services.interpreter.agent.circuit_breaker import DegradedModeBreaker

    app.state.orchestrator = orchestrator
    app.state.session_store = session_store
    app.state.registry = DEFAULT_REGISTRY
    app.state.catalog = catalog
    app.state.breaker = DegradedModeBreaker(
        failure_threshold=2, duration_seconds=60
    )

    app.include_router(interpret_router)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app
