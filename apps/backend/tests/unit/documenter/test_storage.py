"""DocumentStorage tests."""
from __future__ import annotations

import pytest
from google.api_core import exceptions as google_exc

from services.documenter.storage import DocumentStorage
from tests.fakes.fake_gcs_client import FakeGcsClient


@pytest.fixture
def storage_factory():
    def _make(client: FakeGcsClient | None = None) -> tuple[FakeGcsClient, DocumentStorage]:
        c = client or FakeGcsClient()
        s = DocumentStorage(gcs_client=c, bucket_name="b")
        return c, s
    return _make


@pytest.mark.asyncio
async def test_upload_stores_blob_and_returns_signed_url(storage_factory) -> None:
    client, storage = storage_factory()
    url = await storage.upload("abcd1234", "report", b"%PDF-1.4...")
    assert client.stored("b", "documents/abcd1234/report.pdf") == b"%PDF-1.4..."
    assert url.startswith("fake://b/documents/abcd1234/report.pdf")


@pytest.mark.asyncio
async def test_upload_retries_once_on_transient_failure(storage_factory) -> None:
    client = FakeGcsClient(
        fail_sequence=[google_exc.ServiceUnavailable("transient")]
    )
    _, storage = storage_factory(client)
    url = await storage.upload("abcd1234", "drawing", b"%PDF-1.4...")
    assert client.stored("b", "documents/abcd1234/drawing.pdf") == b"%PDF-1.4..."
    assert url.endswith("/drawing.pdf?ttl=24h")


@pytest.mark.asyncio
async def test_upload_hard_fails_after_second_transient_failure(storage_factory) -> None:
    client = FakeGcsClient(
        fail_sequence=[
            google_exc.ServiceUnavailable("first"),
            google_exc.ServiceUnavailable("second"),
        ]
    )
    _, storage = storage_factory(client)
    with pytest.raises(google_exc.ServiceUnavailable):
        await storage.upload("abcd1234", "report", b"%PDF-1.4...")


@pytest.mark.asyncio
async def test_upload_uses_documents_prefix(storage_factory) -> None:
    client, storage = storage_factory()
    await storage.upload("CACHEKEY", "report", b"x")
    assert client.stored("b", "documents/CACHEKEY/report.pdf") == b"x"
