"""Tool-execution node for the current planned step."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import PlanStep
from app.agent.nodes.common import emit_log, log_transition
from app.agent.state import AgentState
from app.core.errors import ToolNotFoundError, ToolTimeoutError
from app.services.metrics import record_tool_call


def _plan_step(state: AgentState, step_index: int) -> PlanStep | None:
    """Return the current plan step when state is well formed."""
    plan = state.get("plan", [])
    if step_index < 0 or step_index >= len(plan):
        return None
    step = plan[step_index]
    if isinstance(step, PlanStep):
        return step
    if isinstance(step, dict):
        return PlanStep.model_validate(step)
    return None


def _tool_data_payload(data: Any) -> dict[str, Any]:
    """Normalize tool output into the dict stored on graph state."""
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    return {"value": data}


async def _finish_tool_call(
    *,
    deps: AgentDependencies,
    tool_name: str,
    step_index: int,
    duration_ms: int,
    status: str,
    level: str,
) -> None:
    await emit_log(
        deps,
        level,
        "executor",
        "tool_call_finished",
        "Tool call finished.",
        tool=tool_name,
        step_index=step_index,
        duration_ms=duration_ms,
        status=status,
    )
    record_tool_call(tool_name, status, duration_ms / 1000.0)


async def execute_tool(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
    """Invoke the registered tool for the current plan step and record the outcome."""
    step_index = state.get("current_step_index", 0)
    step = _plan_step(state, step_index)
    tool_name = step.tool_name if step is not None else "unknown"
    retry_counts = state.get("retry_counts", {})
    attempt = int(retry_counts.get(str(step_index), 0)) + 1

    await emit_log(
        deps,
        "info",
        "executor",
        "tool_call_started",
        "Tool call started.",
        tool=tool_name,
        step_index=step_index,
        attempt=attempt,
    )

    update = await log_transition(
        state,
        deps,
        "execute_tool",
        "running",
        f"Executing tool {tool_name} for plan step {step_index}.",
    )
    update["retry_requested"] = False
    update["skip_requested"] = False

    if step is None:
        message = f"No plan step available at index {step_index}."
        update["last_tool_success"] = False
        update["last_error_type"] = "ToolExecutionError"
        update["skip_requested"] = True
        update["errors"] = [*state.get("errors", []), message]
        update["pending_result"] = {
            "tool_name": tool_name,
            "step_index": step_index,
            "success": False,
            "data": {},
            "error": message,
            "duration_ms": 0,
            "metadata": {},
            "error_type": "ToolExecutionError",
        }
        await _finish_tool_call(
            deps=deps,
            tool_name=tool_name,
            step_index=step_index,
            duration_ms=0,
            status="failed",
            level="error",
        )
        return update

    try:
        tool = deps.tool_registry.get(step.tool_name)
    except ToolNotFoundError as exc:
        message = str(exc)
        update["last_tool_success"] = False
        update["last_error_type"] = ToolNotFoundError.__name__
        update["skip_requested"] = True
        update["errors"] = [*state.get("errors", []), message]
        update["pending_result"] = {
            "tool_name": step.tool_name,
            "step_index": step_index,
            "success": False,
            "data": {},
            "error": message,
            "duration_ms": 0,
            "metadata": {"tool_name": step.tool_name},
            "error_type": ToolNotFoundError.__name__,
        }
        await _finish_tool_call(
            deps=deps,
            tool_name=step.tool_name,
            step_index=step_index,
            duration_ms=0,
            status="failed",
            level="error",
        )
        return update

    tool_result = await tool.execute(step.tool_args)
    data = _tool_data_payload(tool_result.data)
    duration_ms = tool_result.duration_ms
    status = "succeeded" if tool_result.ok else "failed"

    update["last_tool_success"] = tool_result.ok
    update["last_error_type"] = None if tool_result.ok else tool_result.error_type
    update["pending_result"] = {
        "tool_name": step.tool_name,
        "step_index": step_index,
        "success": tool_result.ok,
        "data": data,
        "error": None if tool_result.ok else tool_result.error_message,
        "duration_ms": duration_ms,
        "metadata": dict(tool_result.metadata),
        "error_type": tool_result.error_type,
    }

    if not tool_result.ok:
        message = tool_result.error_message or f"Tool {step.tool_name} failed."
        update["errors"] = [*state.get("errors", []), message]
        if tool_result.error_type == ToolTimeoutError.__name__:
            update["retry_requested"] = True
        else:
            update["skip_requested"] = True

    await _finish_tool_call(
        deps=deps,
        tool_name=step.tool_name,
        step_index=step_index,
        duration_ms=duration_ms,
        status=status,
        level="info" if tool_result.ok else "error",
    )
    return update
