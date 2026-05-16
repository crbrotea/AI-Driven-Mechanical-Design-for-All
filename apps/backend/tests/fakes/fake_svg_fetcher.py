"""Canned SVG fetcher for tests.

Returns the same SVG bytes for any URL, or raises if configured to do so.
"""
from __future__ import annotations

_DEFAULT_SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'


class FakeSvgFetcher:
    def __init__(
        self,
        svg_bytes: bytes = _DEFAULT_SVG,
        raise_on_call: Exception | None = None,
    ) -> None:
        self._svg = svg_bytes
        self._raise = raise_on_call
        self.calls: list[str] = []

    async def fetch(self, url: str) -> bytes:
        self.calls.append(url)
        if self._raise is not None:
            raise self._raise
        return self._svg
