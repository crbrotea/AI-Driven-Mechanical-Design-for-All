"""SVG fetcher used by S5 Documenter to embed section views into PDFs."""
from __future__ import annotations

from typing import Protocol

import httpx


class SvgFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class HttpxSvgFetcher:
    """Production SVG fetcher using httpx (already a backend dep).

    Raises httpx.HTTPError subclasses on transport / status errors. The
    pipeline is responsible for mapping those to a structured DocumentError.
    """

    def __init__(self, timeout_s: float = 5.0) -> None:
        self._timeout_s = timeout_s

    async def fetch(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
