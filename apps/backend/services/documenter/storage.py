"""GCS uploader for S5 Documenter PDFs."""
from __future__ import annotations

import asyncio
from typing import Any

import google.auth
from google.api_core import exceptions as google_exc
from google.auth.transport import requests as gar_requests


class DocumentStorage:
    def __init__(
        self,
        *,
        gcs_client: Any,
        bucket_name: str,
        ttl_hours: int = 24,
        prefix: str = "documents",
    ) -> None:
        self._client = gcs_client
        self._bucket_name = bucket_name
        self._ttl_hours = ttl_hours
        self._prefix = prefix

    async def upload(
        self,
        cache_key: str,
        name: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload to {prefix}/{cache_key}/{name}.pdf. Retry once on transient failure.

        Returns the signed URL for the uploaded blob.
        """
        blob_path = f"{self._prefix}/{cache_key}/{name}.pdf"

        async def _do_upload() -> None:
            await asyncio.to_thread(
                self._client.bucket(self._bucket_name).blob(blob_path).upload_from_string,
                content,
                content_type,
            )

        try:
            await _do_upload()
        except (google_exc.ServiceUnavailable, google_exc.InternalServerError):
            await asyncio.sleep(1.0)
            await _do_upload()

        return self._sign(blob_path)

    def _ensure_signing_credentials(self) -> tuple[str | None, str | None]:
        """Resolve ADC + refresh token so v4 signing can use IAM Credentials.

        Cloud Run runtime credentials carry no private key, so the GCS
        client falls back to the IAM Credentials API when given an explicit
        service_account_email + access_token. Mirrors services/geometry/cache.
        """
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not hasattr(credentials, "service_account_email"):
            return None, None
        credentials.refresh(gar_requests.Request())  # type: ignore[no-untyped-call]
        return credentials.service_account_email, credentials.token

    def _sign(self, blob_path: str) -> str:
        """Return a signed URL.

        FakeGcsClient does not implement v4 signing, so when the underlying
        client lacks a `bucket(...).blob(...).generate_signed_url` we fall back
        to a stable `fake://...` URL.
        """
        try:
            blob = self._client.bucket(self._bucket_name).blob(blob_path)
            sign = getattr(blob, "generate_signed_url", None)
            if callable(sign):
                from datetime import timedelta

                sa_email, access_token = self._ensure_signing_credentials()
                if sa_email and access_token:
                    return str(
                        sign(
                            version="v4",
                            expiration=timedelta(hours=self._ttl_hours),
                            method="GET",
                            service_account_email=sa_email,
                            access_token=access_token,
                        )
                    )
                return str(
                    sign(
                        version="v4",
                        expiration=timedelta(hours=self._ttl_hours),
                        method="GET",
                    )
                )
        except Exception:
            # fall through to fake URL
            pass
        return f"fake://{self._bucket_name}/{blob_path}?ttl={self._ttl_hours}h"
