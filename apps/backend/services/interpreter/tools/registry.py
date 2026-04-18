"""Tool registry: single dispatch point for LLM-initiated tool calls."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolRegistry(BaseModel):
    """Maps tool names to their implementations. LLM cannot escape this set."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tools: dict[str, Callable[[dict[str, Any]], Any]]

    def names(self) -> list[str]:
        return sorted(self.tools.keys())

    def invoke(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self.tools:
            raise KeyError(f"Unknown tool: {name}")
        return self.tools[name](args)
