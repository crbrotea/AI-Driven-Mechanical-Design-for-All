"""System prompt loader + user prompt renderer for the explainer."""
from __future__ import annotations

from pathlib import Path

_SYSTEM_PROMPT_FILENAME = "explainer_system.md"


def load_system_prompt(prompts_dir: Path) -> str:
    """Load the system prompt from `<prompts_dir>/explainer_system.md`."""
    return (prompts_dir / _SYSTEM_PROMPT_FILENAME).read_text(encoding="utf-8")


def build_user_prompt(facts: dict[str, str]) -> str:
    facts_block = "\n".join(f"  {k} = {v}" for k, v in facts.items())
    return f"FACTS:\n{facts_block}\n\nProduce the JSON report now."


def build_strict_retry_prompt(facts: dict[str, str]) -> str:
    base = build_user_prompt(facts)
    return base + "\n\nIMPORTANT: Output ONLY valid JSON. No prose, no code fences."
