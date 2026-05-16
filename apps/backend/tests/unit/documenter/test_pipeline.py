"""Documenter pipeline tests using FakeGcsClient + FakeSvgFetcher."""
from __future__ import annotations

import pytest

from services.documenter.cache import DocumenterCache
from services.documenter.domain.errors import DocumentErrorCode, DocumentException
from services.documenter.domain.models import DocumentRequest
from services.documenter.pipeline import Documenter
from services.documenter.storage import DocumentStorage
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialProperties, MaterialsCatalog
from services.physics.domain.models import AnalysisResult, Verdict
from tests.fakes.fake_gcs_client import FakeGcsClient
from tests.fakes.fake_svg_fetcher import FakeSvgFetcher

_STEEL = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def _catalog() -> MaterialsCatalog:
    return MaterialsCatalog([_STEEL])


def _request() -> DocumentRequest:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )
    analysis = AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159},
    )
    narrative = NaturalReport(
        summary="Near-yield at 3000 rpm.",
        risks=["Stress 77 percent of yield."],
        suggestions=["Verify with FEA."],
        analogies=["Like a sprinter near top speed."],
        facts_used=["stress_max_mpa", "safety_factor"],
    )
    artifacts = CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
        ),
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )
    return DocumentRequest(
        intent=intent, analysis_result=analysis, natural_report=narrative,
        geometry_artifacts=artifacts,
    )


@pytest.mark.asyncio
async def test_pipeline_cache_miss_uploads_both_pdfs() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    deliv = await docter.document(_request())
    assert deliv.cache_hit is False
    assert deliv.report_pdf_url.endswith("/report.pdf?ttl=24h")
    assert deliv.drawing_pdf_url.endswith("/drawing.pdf?ttl=24h")
    assert deliv.step_url == "https://example.com/step"
    assert deliv.glb_url == "https://example.com/glb"
    assert deliv.svg_url == "https://example.com/svg"
    assert gcs.stored("b", f"documents/{deliv.cache_key}/report.pdf") is not None
    assert gcs.stored("b", f"documents/{deliv.cache_key}/drawing.pdf") is not None


@pytest.mark.asyncio
async def test_pipeline_cache_hit_skips_upload() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    first = await docter.document(_request())
    second = await docter.document(_request())

    assert second.cache_hit is True
    assert second.cache_key == first.cache_key
    assert second.report_pdf_url == first.report_pdf_url


@pytest.mark.asyncio
async def test_pipeline_unknown_material_raises_invalid_input() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=MaterialsCatalog([]),
                        svg_fetcher=fetcher)

    with pytest.raises(DocumentException) as ei:
        await docter.document(_request())
    assert ei.value.error.code is DocumentErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_pipeline_svg_fetch_failure_maps_to_invalid_input() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher(raise_on_call=RuntimeError("no svg"))
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    with pytest.raises(DocumentException) as ei:
        await docter.document(_request())
    assert ei.value.error.code is DocumentErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_pipeline_deliverables_echoes_geometry_urls() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    deliv = await docter.document(_request())
    assert deliv.step_url == "https://example.com/step"
    assert deliv.glb_url == "https://example.com/glb"
    assert deliv.svg_url == "https://example.com/svg"


@pytest.mark.asyncio
async def test_pipeline_records_fetcher_call_with_svg_url() -> None:
    gcs = FakeGcsClient()
    storage = DocumentStorage(gcs_client=gcs, bucket_name="b")
    cache = DocumenterCache()
    fetcher = FakeSvgFetcher()
    docter = Documenter(storage=storage, cache=cache, materials_catalog=_catalog(),
                        svg_fetcher=fetcher)

    await docter.document(_request())
    assert fetcher.calls == ["https://example.com/svg"]
