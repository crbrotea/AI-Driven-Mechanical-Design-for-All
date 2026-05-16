"""Solvers registry: intent.type -> solver function."""
from __future__ import annotations

from collections.abc import Callable

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode
from services.physics.domain.models import AnalysisResult, LoadCase
from services.physics.solvers.flywheel import solve_flywheel
from services.physics.solvers.hydro import solve_hydro
from services.physics.solvers.shelter import solve_shelter

Solver = Callable[[dict[str, float], LoadCase, MaterialProperties], AnalysisResult]

SOLVERS: dict[str, Solver] = {
    "Flywheel_Rim": solve_flywheel,
    "Pelton_Runner": solve_hydro,
    "Hinge_Panel": solve_shelter,
}


def get_solver(intent_type: str) -> Solver:
    """Resolve the solver for an intent type. Raises AnalysisException on unknown."""
    solver = SOLVERS.get(intent_type)
    if solver is None:
        AnalysisError(
            code=AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE,
            message=f"No solver registered for intent.type={intent_type!r}",
            intent_type=intent_type,
        ).raise_as()
        raise AssertionError("unreachable")  # type-narrowing
    return solver
