"""Stub failure recovery node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.nodes.common import emit_log, log_transition
from app.agent.state import AgentState
from app.services.metrics import retries_total


async def retry_or_fallback(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Record a recovery attempt; routing policy is implemented by pure functions."""
    update = await log_transition(
        state,
        deps,
        "retry_or_fallback",
        "running",
        "Failure recovery decision delegated to graph routing.",
    )
    if state.get("retry_requested", False):
        retry_counts = state.get("retry_counts", {})
        retry_count = retry_counts.get(str(state.get("current_step_index", 0)), 0)
        backoff_ms = max(0, int(100 * (2**retry_count)))
        await emit_log(
            deps,
            "warn",
            "executor",
            "retry_scheduled",
            "A tool retry was scheduled.",
            retry_count=retry_count + 1,
            backoff_ms=backoff_ms,
        )
        retries_total.inc()
    if state.get("skip_requested", False):
        await emit_log(
            deps,
            "warn",
            "executor",
            "fallback_applied",
            "The current failed step will be skipped.",
            step_index=state.get("current_step_index", 0),
        )
    return update
