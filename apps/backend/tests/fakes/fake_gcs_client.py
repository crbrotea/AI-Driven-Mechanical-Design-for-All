"""In-memory stand-in for google.cloud.storage.Client.

Records every uploaded blob and supports injecting transient failures so that
DocumentStorage.upload can be tested for its retry-once behavior.
"""
from __future__ import annotations

from collections.abc import Iterable


class _FakeBlob:
    def __init__(
        self,
        bucket_name: str,
        name: str,
        store: dict[tuple[str, str], bytes],
        fail_remaining: list[Exception],
    ) -> None:
        self._bucket_name = bucket_name
        self._name = name
        self._store = store
        self._fail_remaining = fail_remaining

    def upload_from_string(self, content: bytes, content_type: str) -> None:
        if self._fail_remaining:
            raise self._fail_remaining.pop(0)
        self._store[(self._bucket_name, self._name)] = content


class _FakeBucket:
    def __init__(
        self,
        name: str,
        store: dict[tuple[str, str], bytes],
        fail_remaining: list[Exception],
    ) -> None:
        self.name = name
        self._store = store
        self._fail_remaining = fail_remaining

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(self.name, name, self._store, self._fail_remaining)


class FakeGcsClient:
    """Minimal subset of google.cloud.storage.Client used by DocumentStorage."""

    def __init__(self, *, fail_sequence: Iterable[Exception] | None = None) -> None:
        self._store: dict[tuple[str, str], bytes] = {}
        self._fail_remaining: list[Exception] = list(fail_sequence or [])
        self.upload_attempts = 0

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(name, self._store, self._fail_remaining_view())

    def _fail_remaining_view(self) -> list[Exception]:
        """Shared list reference so the blob can pop from it.

        Also increments upload_attempts as a side effect when storage tries.
        """
        return self._fail_remaining

    def stored(self, bucket: str, name: str) -> bytes | None:
        return self._store.get((bucket, name))
