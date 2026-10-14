"""Stub analysis node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import Analysis
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


async def analyzer(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Create an empty but valid analysis for a stub graph run."""
    update = await log_transition(
        state, deps, "analyzer", "analyzing", "Stub analysis node completed."
    )
    update["analysis"] = Analysis(
        summary="Stub analysis completed; no factual conclusions were generated.",
        findings=[],
    )
    return update
