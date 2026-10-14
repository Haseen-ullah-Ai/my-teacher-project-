"""Stub request-intake node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import ParsedTask
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


async def intake(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Normalize the task into an initial parsed-task representation."""
    update = await log_transition(state, deps, "intake", "pending", "Task accepted for research.")
    task = state.get("task", "")
    update["parsed_task"] = ParsedTask(
        objective=task,
        entities=[],
        constraints=[],
        expected_outputs=["evidence-backed research report"],
    )
    return update
