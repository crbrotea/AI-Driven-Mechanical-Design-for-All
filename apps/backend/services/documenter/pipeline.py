"""Orchestrator for S5 Documenter: cache -> fetch -> compose -> project ->
build -> upload."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from services.documenter.cache import DocumenterCache
from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
    DocumentException,
)
from services.documenter.domain.models import Deliverables, DocumentRequest
from services.documenter.pdf.drawing import build_drawing_pdf
from services.documenter.pdf.report import build_report_pdf
from services.documenter.storage import DocumentStorage
from services.documenter.svg_fetcher import SvgFetcher
from services.documenter.views import project_views
from services.geometry.composer import compose_assembly
from services.interpreter.domain.materials import MaterialsCatalog


class Documenter:
    def __init__(
        self,
        *,
        storage: DocumentStorage,
        cache: DocumenterCache,
        materials_catalog: MaterialsCatalog,
        svg_fetcher: SvgFetcher,
    ) -> None:
        self._storage = storage
        self._cache = cache
        self._materials = materials_catalog
        self._fetcher = svg_fetcher

    async def document(self, req: DocumentRequest) -> Deliverables:
        cache_key = DocumenterCache.key_for(
            req.intent, req.analysis_result, req.natural_report
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.model_copy(update={"cache_hit": True})

        try:
            material = self._materials.get(req.analysis_result.material_name)
        except KeyError:
            DocumentError(
                code=DocumentErrorCode.INVALID_INPUT,
                message=f"unknown material {req.analysis_result.material_name!r}",
                field="analysis_result.material_name",
            ).raise_as()
            raise AssertionError("unreachable") from None

        try:
            svg_bytes = await self._fetcher.fetch(req.geometry_artifacts.svg_url)
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.INVALID_INPUT,
                message=f"failed to fetch svg from url: {exc!r}",
                field="geometry_artifacts.svg_url",
                details={"url": req.geometry_artifacts.svg_url},
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            compound = compose_assembly(req.intent)
        except DocumentException:
            raise
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.GEOMETRY_REBUILD_FAILED,
                message=f"compose_assembly failed: {exc!r}",
                stage="compose",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        views = project_views(compound)

        now_utc_iso = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            report_bytes = build_report_pdf(
                intent=req.intent,
                analysis=req.analysis_result,
                narrative=req.natural_report,
                geometry=req.geometry_artifacts,
                material=material,
                svg_bytes=svg_bytes,
                now_utc_iso=now_utc_iso,
                cache_key=cache_key,
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.REPORT_BUILD_FAILED,
                message=f"build_report_pdf failed: {exc!r}",
                stage="build_report",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            drawing_bytes = build_drawing_pdf(
                views=views,
                mass=req.geometry_artifacts.mass_properties,
                intent=req.intent,
                material=material,
                now_utc_iso=now_utc_iso,
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.DRAWING_BUILD_FAILED,
                message=f"build_drawing_pdf failed: {exc!r}",
                stage="build_drawing",
            ).raise_as()
            raise AssertionError("unreachable") from exc

        try:
            report_url, drawing_url = await asyncio.gather(
                self._storage.upload(cache_key, "report", report_bytes),
                self._storage.upload(cache_key, "drawing", drawing_bytes),
            )
        except Exception as exc:
            DocumentError(
                code=DocumentErrorCode.GCS_UPLOAD_FAILED,
                message=f"GCS upload failed after retry: {exc!r}",
                stage="upload",
                retry_after=5,
            ).raise_as()
            raise AssertionError("unreachable") from exc

        deliv = Deliverables(
            report_pdf_url=report_url,
            drawing_pdf_url=drawing_url,
            step_url=req.geometry_artifacts.step_url,
            glb_url=req.geometry_artifacts.glb_url,
            svg_url=req.geometry_artifacts.svg_url,
            cache_hit=False,
            cache_key=cache_key,
        )
        self._cache.put(cache_key, deliv)
        return deliv
