"""Stub report-generation node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.nodes.common import emit_log, log_transition
from app.agent.state import AgentState
from app.tools.schemas import ReportDraft


async def reporter(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Create a valid placeholder report and complete the run."""
    update = await log_transition(
        state, deps, "reporter", "reporting", "Stub report generation started."
    )
    update["report"] = ReportDraft(
        title="ResearchPilot Stub Report",
        executive_summary="This report confirms the agent graph completed its stub workflow.",
        sections=[],
        findings=[],
        recommendations=[],
        limitations=["Stage 6 graph nodes are stubs; no real tool execution occurred."],
    )
    update["completed"] = True
    run_id = state.get("run_id")
    if run_id is not None:
        await deps.run_logger.log_node(
            run_id, "reporter", "completed", "Stub report generated; run completed."
        )
    await emit_log(
        deps,
        "info",
        "reporter",
        "run_completed",
        "Research run completed.",
    )
    update["status"] = "completed"
    return update
