"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to tests/fixtures/."""
    return FIXTURES_DIR
