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
