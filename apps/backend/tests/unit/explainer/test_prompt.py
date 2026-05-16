"""Prompt loader + builder tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.explainer.prompt import (
    build_strict_retry_prompt,
    build_user_prompt,
    load_system_prompt,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def test_load_system_prompt_carries_anti_fabrication_rule() -> None:
    text = load_system_prompt(_PROMPTS_DIR)
    assert "NEVER invent" in text
    assert "FACTS table" in text
    assert "facts_used" in text


def test_load_system_prompt_describes_schema() -> None:
    text = load_system_prompt(_PROMPTS_DIR)
    assert "summary" in text
    assert "risks" in text
    assert "suggestions" in text
    assert "analogies" in text


def test_build_user_prompt_embeds_facts_table() -> None:
    facts = {"stress_max_mpa": "193.70 MPa", "safety_factor": "1.29"}
    rendered = build_user_prompt(facts)
    assert "FACTS:" in rendered
    assert "stress_max_mpa = 193.70 MPa" in rendered
    assert "safety_factor = 1.29" in rendered
    assert "Produce the JSON report now." in rendered


def test_build_strict_retry_prompt_appends_strict_instruction() -> None:
    facts = {"verdict": "WARN"}
    base = build_user_prompt(facts)
    strict = build_strict_retry_prompt(facts)
    assert strict.startswith(base)
    assert "Output ONLY valid JSON" in strict


def test_load_system_prompt_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_system_prompt(Path("/no/such/dir"))
