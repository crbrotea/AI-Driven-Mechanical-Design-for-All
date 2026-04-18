"""Intent hasher and GeometryCache (FakeGeometryCache + GcsGeometryCache)."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Protocol

from services.geometry.domain.artifacts import (
    BuiltArtifacts,
    CachedArtifacts,
    MassProperties,
)
from services.geometry.domain.errors import GeometryError, GeometryErrorCode
from services.interpreter.domain.intent import DesignIntent


def compute_intent_hash(intent: DesignIntent) -> str:
    """Hash only the VALUES (not tri-state metadata) in a deterministic way."""
    canonical = {
        "type": intent.type,
        "fields": {k: intent.fields[k].value for k in sorted(intent.fields.keys())},
        "composed_of": sorted(intent.composed_of),
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class GeometryCacheProtocol(Protocol):
    async def lookup(self, intent_hash: str) -> CachedArtifacts | None: ...
    async def store(
        self, intent_hash: str, artifacts: BuiltArtifacts
    ) -> CachedArtifacts: ...


class FakeGeometryCache:
    """In-memory cache for unit/component tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[BuiltArtifacts, CachedArtifacts]] = {}

    async def lookup(self, intent_hash: str) -> CachedArtifacts | None:
        pair = self._store.get(intent_hash)
        return pair[1] if pair else None

    async def store(
        self, intent_hash: str, artifacts: BuiltArtifacts
    ) -> CachedArtifacts:
        cached = CachedArtifacts(
            mass_properties=artifacts.mass,
            step_url=f"fake://cache/{intent_hash}/geometry.step",
            glb_url=f"fake://cache/{intent_hash}/geometry.glb",
            svg_url=f"fake://cache/{intent_hash}/section.svg",
        )
        self._store[intent_hash] = (artifacts, cached)
        return cached


class GcsGeometryCache:
    """Google Cloud Storage-backed implementation."""

    def __init__(
        self,
        gcs_client: Any,
        bucket_name: str,
        ttl_hours: int = 24,
    ) -> None:
        self._client = gcs_client
        self._bucket_name = bucket_name
        self._ttl = timedelta(hours=ttl_hours)

    def _bucket(self) -> Any:
        return self._client.bucket(self._bucket_name)

    def _signed_url(self, blob_name: str) -> str:
        blob = self._bucket().blob(blob_name)
        return str(blob.generate_signed_url(expiration=self._ttl))

    async def lookup(self, intent_hash: str) -> CachedArtifacts | None:
        mass_blob = self._bucket().blob(f"cache/{intent_hash}/mass.json")
        if not mass_blob.exists():
            return None
        try:
            mass_json = mass_blob.download_as_text()
            mass = MassProperties.model_validate_json(mass_json)
        except Exception:
            return None  # corruption → treat as miss
        return CachedArtifacts(
            mass_properties=mass,
            step_url=self._signed_url(f"cache/{intent_hash}/geometry.step"),
            glb_url=self._signed_url(f"cache/{intent_hash}/geometry.glb"),
            svg_url=self._signed_url(f"cache/{intent_hash}/section.svg"),
        )

    async def store(
        self, intent_hash: str, artifacts: BuiltArtifacts
    ) -> CachedArtifacts:
        try:
            self._bucket().blob(f"cache/{intent_hash}/geometry.step").upload_from_string(
                artifacts.step_bytes, content_type="application/step"
            )
            self._bucket().blob(f"cache/{intent_hash}/geometry.glb").upload_from_string(
                artifacts.glb_bytes, content_type="model/gltf-binary"
            )
            self._bucket().blob(f"cache/{intent_hash}/section.svg").upload_from_string(
                artifacts.svg_bytes, content_type="image/svg+xml"
            )
            self._bucket().blob(f"cache/{intent_hash}/mass.json").upload_from_string(
                artifacts.mass.model_dump_json(), content_type="application/json"
            )
        except Exception as e:
            GeometryError(
                code=GeometryErrorCode.GCS_UPLOAD_FAILED,
                message=f"Failed to upload artifacts for {intent_hash}: {e}",
                stage="upload",
            ).raise_as()

        return CachedArtifacts(
            mass_properties=artifacts.mass,
            step_url=self._signed_url(f"cache/{intent_hash}/geometry.step"),
            glb_url=self._signed_url(f"cache/{intent_hash}/geometry.glb"),
            svg_url=self._signed_url(f"cache/{intent_hash}/section.svg"),
        )
