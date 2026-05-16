"""Vertex sentinel exceptions used by the explainer to map Vertex failures."""
from __future__ import annotations

from services.interpreter.agent.gemma_client import VertexRateLimited, VertexTimeout


def test_vertex_timeout_is_runtime_error() -> None:
    err = VertexTimeout("Vertex took too long")
    assert isinstance(err, RuntimeError)
    assert str(err) == "Vertex took too long"


def test_vertex_rate_limited_is_runtime_error() -> None:
    err = VertexRateLimited("quota exhausted")
    assert isinstance(err, RuntimeError)
    assert str(err) == "quota exhausted"


def test_sentinels_are_distinct() -> None:
    assert VertexTimeout is not VertexRateLimited
    assert not issubclass(VertexTimeout, VertexRateLimited)
    assert not issubclass(VertexRateLimited, VertexTimeout)
