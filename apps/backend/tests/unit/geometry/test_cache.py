"""Unit tests for GeometryCache and intent hasher."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.geometry.cache import (
    FakeGeometryCache,
    GcsGeometryCache,
    compute_intent_hash,
)
from services.geometry.domain.artifacts import (
    BuiltArtifacts,
    MassProperties,
)
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def _intent(type_: str, **fields: float) -> DesignIntent:
    return DesignIntent(
        type=type_,
        fields={
            name: TriStateField(value=v, source=FieldSource.EXTRACTED)
            for name, v in fields.items()
        },
    )


def test_hash_ignores_tri_state_metadata() -> None:
    i1 = DesignIntent(type="Shaft", fields={
        "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
    })
    i2 = DesignIntent(type="Shaft", fields={
        "diameter_m": TriStateField(value=0.05, source=FieldSource.DEFAULTED, reason="x"),
    })
    assert compute_intent_hash(i1) == compute_intent_hash(i2)


def test_hash_changes_on_value_change() -> None:
    assert compute_intent_hash(_intent("Shaft", diameter_m=0.05, length_m=0.5)) != \
           compute_intent_hash(_intent("Shaft", diameter_m=0.06, length_m=0.5))


def test_hash_is_16_chars() -> None:
    h = compute_intent_hash(_intent("Shaft", diameter_m=0.05, length_m=0.5))
    assert len(h) == 16


def test_hash_ignores_composed_order() -> None:
    i1 = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=["Shaft", "Bearing_Housing"],
    )
    i2 = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=["Bearing_Housing", "Shaft"],
    )
    assert compute_intent_hash(i1) == compute_intent_hash(i2)


async def test_fake_cache_miss_returns_none() -> None:
    cache = FakeGeometryCache()
    result = await cache.lookup("nonexistent")
    assert result is None


async def test_fake_cache_store_then_lookup_roundtrip() -> None:
    cache = FakeGeometryCache()
    mass = MassProperties(
        volume_m3=0.01, mass_kg=78.5,
        center_of_mass=(0, 0, 0.025),
        bbox_m=(0, 0, 0, 0.5, 0.5, 0.05),
    )
    artifacts = BuiltArtifacts(
        step_bytes=b"ISO-10303-21;",
        glb_bytes=b"glTF",
        svg_bytes=b"<svg></svg>",
        mass=mass,
    )
    await cache.store("abc123", artifacts)
    result = await cache.lookup("abc123")
    assert result is not None
    assert result.mass_properties.mass_kg == 78.5


# ---------------------------------------------------------------------------
# GcsGeometryCache — unit tests
# ---------------------------------------------------------------------------

def _make_mass() -> MassProperties:
    return MassProperties(
        volume_m3=0.001,
        mass_kg=7.85,
        center_of_mass=(0.0, 0.0, 0.05),
        bbox_m=(0.0, 0.0, 0.0, 0.1, 0.1, 0.1),
    )


def _make_artifacts() -> BuiltArtifacts:
    return BuiltArtifacts(
        step_bytes=b"STEP",
        glb_bytes=b"GLB",
        svg_bytes=b"<svg/>",
        mass=_make_mass(),
    )


def _make_gcs_cache(mock_client: MagicMock) -> GcsGeometryCache:
    return GcsGeometryCache(gcs_client=mock_client, bucket_name="test-bucket", ttl_hours=1)


async def test_gcs_cache_upload_is_called_4_times() -> None:
    """store() must upload exactly 4 blobs with the correct content_types."""
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed-url"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    cache = _make_gcs_cache(mock_client)

    # Patch _ensure_signing_credentials so _signed_url does not need real GCP
    with patch.object(cache, "_ensure_signing_credentials", return_value=(None, None)):
        await cache.store("deadbeef", _make_artifacts())

    assert mock_blob.upload_from_string.call_count == 4
    content_types_used = {
        call.kwargs.get("content_type") or call.args[1]
        for call in mock_blob.upload_from_string.call_args_list
    }
    assert content_types_used == {
        "application/step",
        "model/gltf-binary",
        "image/svg+xml",
        "application/json",
    }


async def test_gcs_cache_lookup_miss_when_blob_absent() -> None:
    """lookup() returns None without downloading when the mass blob does not exist."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    cache = _make_gcs_cache(mock_client)
    result = await cache.lookup("deadbeef")

    assert result is None
    mock_blob.download_as_text.assert_not_called()


async def test_gcs_cache_lookup_handles_corruption_as_miss() -> None:
    """lookup() treats malformed JSON in mass.json as a cache miss."""
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_text.return_value = "not valid json {"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    cache = _make_gcs_cache(mock_client)
    result = await cache.lookup("deadbeef")

    assert result is None


async def test_gcs_cache_uses_v4_signing_when_sa_email_available() -> None:
    """_signed_url() passes version='v4' and SA email+token when ADC has SA creds."""
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://v4-signed-url"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    cache = _make_gcs_cache(mock_client)

    fake_sa_email = "sa@project.iam.gserviceaccount.com"
    fake_token = "ya29.fake-token"

    with patch.object(
        cache,
        "_ensure_signing_credentials",
        return_value=(fake_sa_email, fake_token),
    ):
        url = cache._signed_url("cache/deadbeef/geometry.step")

    assert url == "https://v4-signed-url"
    mock_blob.generate_signed_url.assert_called_once()
    call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
    assert call_kwargs["version"] == "v4"
    assert call_kwargs["service_account_email"] == fake_sa_email
    assert call_kwargs["access_token"] == fake_token
