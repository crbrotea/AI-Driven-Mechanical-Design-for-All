"""Settings loaded from environment variables (Pydantic Settings)."""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.providers.env import EnvSettingsSource


class _CsvEnvSource(EnvSettingsSource):
    """Env source that parses comma-separated strings into list[str] fields."""

    _CSV_FIELDS: ClassVar[frozenset[str]] = frozenset({"cors_allowed_origins"})

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name in self._CSV_FIELDS and isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        sources = super().settings_customise_sources(
            settings_cls,
            init_settings=init_settings,
            env_settings=env_settings,
            dotenv_settings=dotenv_settings,
            file_secret_settings=file_secret_settings,
        )
        return tuple(
            _CsvEnvSource(settings_cls) if isinstance(s, EnvSettingsSource) else s
            for s in sources
        )
