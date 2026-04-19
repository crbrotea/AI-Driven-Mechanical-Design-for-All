"""Pipeline orchestrator — ties composer + exporters + cache together.

Yields progress events as an async generator; the router consumes them
and emits SSE events to the client.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from services.geometry.api.dto import GenerateArtifactUrls, GenerateResponse
from services.geometry.cache import (
    GeometryCacheProtocol,
    compute_intent_hash,
)
from services.geometry.composer import compose_assembly
from services.geometry.domain.artifacts import BuiltArtifacts
from services.geometry.domain.errors import GeometryError, GeometryErrorCode
from services.geometry.exporters.glb import export_glb
from services.geometry.exporters.mass import compute_mass_properties
from services.geometry.exporters.step import export_step
from services.geometry.exporters.svg import export_svg
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialsCatalog


class GeometryPipeline:
    """Deterministic CAD build pipeline with cache-through semantics."""

    def __init__(
        self,
        cache: GeometryCacheProtocol,
        materials_catalog: MaterialsCatalog,
    ) -> None:
        self._cache = cache
        self._catalog = materials_catalog

    async def generate(
        self,
        *,
        intent: DesignIntent,
        material_name: str,
    ) -> GenerateResponse:
        """Run the full pipeline (no streaming — used for tests)."""
        async for ev in self.generate_streaming(intent=intent, material_name=material_name):
            if ev["event"] == "final":
                return GenerateResponse.model_validate(ev["data"])
        raise RuntimeError("pipeline ended without emitting final event")

    async def generate_streaming(
        self,
        *,
        intent: DesignIntent,
        material_name: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the pipeline and yield progress+final events as dicts."""
        try:
            material = self._catalog.get(material_name)
        except KeyError:
            GeometryError(
                code=GeometryErrorCode.MATERIAL_NOT_FOUND,
                message=f"Material '{material_name}' not found.",
                details={"material_name": material_name},
            ).raise_as()

        intent_hash = compute_intent_hash(intent)
        yield {"event": "progress", "data": {"step": "cache_lookup", "pct": 5}}
        cached = await self._cache.lookup(intent_hash)
        if cached is not None:
            yield {
                "event": "final",
                "data": GenerateResponse(
                    cache_hit=True,
                    intent_hash=intent_hash,
                    artifacts=GenerateArtifactUrls(
                        step_url=cached.step_url,
                        glb_url=cached.glb_url,
                        svg_url=cached.svg_url,
                    ),
                    mass_properties=cached.mass_properties,
                    material_name=material.name,
                    material_density_kg_m3=material.density_kg_m3,
                ).model_dump(),
            }
            return

        # GCS miss — try demo fallback before triggering a full rebuild.
        # This is the GCS-down safety net: hero intents with pre-generated
        # artifacts on disk are served without touching GCS at all.
        from services.geometry.fallback import lookup_demo_fallback
        cached = await lookup_demo_fallback(intent_hash)
        if cached is not None:
            yield {"event": "progress", "data": {"step": "fallback_hit", "pct": 10}}
            yield {
                "event": "final",
                "data": GenerateResponse(
                    cache_hit=True,  # treat fallback as cache-hit for the client
                    intent_hash=intent_hash,
                    artifacts=GenerateArtifactUrls(
                        step_url=cached.step_url,
                        glb_url=cached.glb_url,
                        svg_url=cached.svg_url,
                    ),
                    mass_properties=cached.mass_properties,
                    material_name=material.name,
                    material_density_kg_m3=material.density_kg_m3,
                ).model_dump(),
            }
            return

        yield {"event": "progress", "data": {"step": "building_main", "pct": 15,
                                             "primitive": intent.type}}
        compound = compose_assembly(intent)

        yield {"event": "progress", "data": {"step": "fusing_assembly", "pct": 40}}

        yield {"event": "progress", "data": {"step": "exporting", "pct": 60}}
        with TemporaryDirectory() as td:
            tmp = Path(td)
            step_path = tmp / "g.step"
            glb_path = tmp / "g.glb"
            svg_path = tmp / "g.svg"

            await asyncio.gather(
                asyncio.to_thread(export_step, compound, step_path),
                asyncio.to_thread(export_glb, compound, glb_path),
                asyncio.to_thread(export_svg, compound, svg_path),
            )

            mass = compute_mass_properties(compound, material)
            artifacts = BuiltArtifacts(
                step_bytes=step_path.read_bytes(),
                glb_bytes=glb_path.read_bytes(),
                svg_bytes=svg_path.read_bytes(),
                mass=mass,
            )

        yield {"event": "progress", "data": {"step": "uploading", "pct": 90}}
        cached = await self._cache.store(intent_hash, artifacts)

        yield {
            "event": "final",
            "data": GenerateResponse(
                cache_hit=False,
                intent_hash=intent_hash,
                artifacts=GenerateArtifactUrls(
                    step_url=cached.step_url,
                    glb_url=cached.glb_url,
                    svg_url=cached.svg_url,
                ),
                mass_properties=cached.mass_properties,
                material_name=material.name,
                material_density_kg_m3=material.density_kg_m3,
            ).model_dump(),
        }
