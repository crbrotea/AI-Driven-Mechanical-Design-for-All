"""Load prompts from disk. Prompts MUST live in markdown files, never in code."""
from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT_FILENAME = "interpreter_system.md"


def load_system_prompt(prompts_dir: Path) -> str:
    """Return the contents of the interpreter system prompt markdown file.

    Raises FileNotFoundError if the prompt file is missing.
    """
    path = prompts_dir / SYSTEM_PROMPT_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"System prompt not found at {path}. Did you create prompts/interpreter_system.md?"
        )
    return path.read_text(encoding="utf-8")
