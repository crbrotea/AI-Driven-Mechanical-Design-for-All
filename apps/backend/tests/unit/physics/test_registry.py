"""Solvers registry tests - dispatch + UNSUPPORTED_INTENT_TYPE."""
from __future__ import annotations

import pytest

from services.physics.domain.errors import AnalysisErrorCode, AnalysisException
from services.physics.solvers.flywheel import solve_flywheel
from services.physics.solvers.hydro import solve_hydro
from services.physics.solvers.shelter import solve_shelter
from services.physics.solvers_registry import SOLVERS, get_solver


def test_registry_covers_three_heroes() -> None:
    assert SOLVERS["Flywheel_Rim"] is solve_flywheel
    assert SOLVERS["Pelton_Runner"] is solve_hydro
    assert SOLVERS["Hinge_Panel"] is solve_shelter


def test_get_solver_unknown_raises() -> None:
    with pytest.raises(AnalysisException) as ei:
        get_solver("Shaft")
    assert ei.value.error.code is AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE
    assert ei.value.error.intent_type == "Shaft"


def test_get_solver_returns_callable() -> None:
    assert get_solver("Flywheel_Rim") is solve_flywheel
