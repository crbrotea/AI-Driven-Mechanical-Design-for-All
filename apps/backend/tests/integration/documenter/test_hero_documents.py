"""End-to-end S5 integration over the three hero bundles."""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_hero_flywheel_document_bundles_all_artifacts(
    document_client, hero_flywheel_request
) -> None:
    r = document_client.post("/document", json=hero_flywheel_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")
    assert d["step_url"] == hero_flywheel_request["geometry_artifacts"]["step_url"]
    assert d["cache_hit"] is False


@pytest.mark.integration
def test_hero_hydro_document_bundles_all_artifacts(
    document_client, hero_hydro_request
) -> None:
    r = document_client.post("/document", json=hero_hydro_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")


@pytest.mark.integration
def test_hero_shelter_document_bundles_all_artifacts(
    document_client, hero_shelter_request
) -> None:
    r = document_client.post("/document", json=hero_shelter_request)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["report_pdf_url"].endswith("/report.pdf?ttl=24h")
    assert d["drawing_pdf_url"].endswith("/drawing.pdf?ttl=24h")
