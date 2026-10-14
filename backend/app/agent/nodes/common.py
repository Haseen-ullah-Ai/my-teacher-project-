"""Helpers shared by stub graph nodes."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState


async def log_transition(
    state: AgentState,
    deps: AgentDependencies,
    node: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    """Log the node transition and return its standard status update."""
    run_id = state.get("run_id")
    if run_id is not None:
        await deps.run_logger.log_node(run_id, node, status, message)
    timestamps = dict(state.get("timestamps", {}))
    timestamps["updated_at"] = datetime.now(UTC)
    return {"status": status, "timestamps": timestamps}


async def instrumented_node(
    state: AgentState,
    deps: AgentDependencies,
    node: str,
    callback: Callable[[AgentState, AgentDependencies], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Log node boundaries, execute a node, and flush logs even on failure."""
    started = time.perf_counter()
    await emit_log(
        deps,
        "info",
        node,
        "node_started",
        f"{node} node started.",
    )
    await flush_logs(deps)
    try:
        update = await callback(state, deps)
    except Exception as exc:
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        await emit_log(
            deps,
            "error",
            node,
            "node_failed",
            f"{node} node failed.",
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        await flush_logs(deps)
        raise
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    await emit_log(
        deps,
        "info",
        node,
        "node_finished",
        f"{node} node finished.",
        duration_ms=duration_ms,
    )
    await flush_logs(deps)
    return update


async def emit_log(
    deps: AgentDependencies,
    level: str,
    node: str,
    event: str,
    message: str,
    **data: Any,
) -> None:
    """Emit an instrumentation event when the logger supports structured levels."""
    method = getattr(deps.run_logger, level, None)
    if method is not None:
        await method(node, event, message, **data)


async def flush_logs(deps: AgentDependencies) -> None:
    """Flush a logger at node boundaries when it provides batching."""
    flush = getattr(deps.run_logger, "flush", None)
    if flush is not None:
        await flush()
