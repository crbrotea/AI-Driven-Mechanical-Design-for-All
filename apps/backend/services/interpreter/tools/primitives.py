"""Gemma 4 tools for primitive discovery and schema retrieval."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.interpreter.domain.primitives_registry import PrimitivesRegistry


def list_primitives(registry: PrimitivesRegistry) -> list[dict[str, Any]]:
    """Tool: return a summary of every registered primitive."""
    return [s.model_dump() for s in registry.list_summaries()]


def get_primitive_schema(
    registry: PrimitivesRegistry, *, name: str
) -> dict[str, Any]:
    """Tool: return the full schema of primitive `name`."""
    return registry.get(name).model_dump()


def build_primitives_tools(
    registry: PrimitivesRegistry,
) -> dict[str, Callable[..., Any]]:
    """Return tool callables bound to the given registry."""
    return {
        "list_primitives": lambda args: list_primitives(registry),
        "get_primitive_schema": lambda args: get_primitive_schema(
            registry, name=args["name"]
        ),
    }
