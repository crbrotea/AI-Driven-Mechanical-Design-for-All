"""Unit tests for the prompt loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.agent.prompt_loader import load_system_prompt


def test_load_system_prompt_returns_full_text() -> None:
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    prompt = load_system_prompt(prompts_dir)
    assert "Role" in prompt
    assert "Tools Protocol" in prompt
    assert "Output Contract" in prompt
    assert "tri-state" in prompt.lower()
    assert "list_primitives" in prompt
    assert len(prompt) > 500


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_system_prompt(tmp_path)
