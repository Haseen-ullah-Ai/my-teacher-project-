"""Stub validation node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import ValidationResult
from app.agent.nodes.common import emit_log, log_transition
from app.agent.state import AgentState


async def validator(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Mark the stub analysis as accepted for graph-topology testing."""
    update = await log_transition(state, deps, "validator", "validating", "Stub validation passed.")
    validation = state.get("validation") or ValidationResult(passed=True, checks=[])
    update["validation"] = validation
    update["validation_feedback"] = validation.feedback
    await emit_log(
        deps,
        "info",
        "validator",
        "validation_check",
        "Stub validation passed.",
        check="stub_validation",
        passed=validation.passed,
    )
    if not validation.passed:
        await emit_log(
            deps,
            "warn",
            "validator",
            "replan_triggered",
            "Validation failed; the graph will consider a bounded replan.",
            feedback=validation.feedback,
        )
    return update
