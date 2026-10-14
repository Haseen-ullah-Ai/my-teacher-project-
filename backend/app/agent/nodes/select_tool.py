"""Stub next-step selection node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


async def select_tool(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Select the current step without invoking its tool."""
    return await log_transition(
        state,
        deps,
        "select_tool",
        "running",
        f"Selected plan step {state.get('current_step_index', 0)}.",
    )
