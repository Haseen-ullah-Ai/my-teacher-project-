"""Stub plan-generation node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import PlanStep
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


async def planner(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Produce a minimal local-tool plan for exercising graph topology."""
    status = "planning"
    update = await log_transition(
        state, deps, "planner", status, "Created a one-step stub research plan."
    )
    if not state.get("plan"):
        update["plan"] = [
            PlanStep(
                index=0,
                description="Stub data-gathering step for graph execution.",
                tool_name="document_search",
                tool_args={"query": state.get("task", "research"), "top_k": 1},
            )
        ]
    return update
