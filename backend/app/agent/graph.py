"""LangGraph topology and pure conditional routing for research runs."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.nodes.analyzer import analyzer
from app.agent.nodes.collect import collect
from app.agent.nodes.common import instrumented_node
from app.agent.nodes.execute_tool import execute_tool
from app.agent.nodes.intake import intake
from app.agent.nodes.planner import planner
from app.agent.nodes.reporter import reporter
from app.agent.nodes.retry_or_fallback import retry_or_fallback
from app.agent.nodes.select_tool import select_tool
from app.agent.nodes.validator import validator
from app.agent.state import AgentState
from app.core.config import settings
from app.core.errors import ToolTimeoutError

Route = Literal[
    "execute_tool",
    "collect",
    "analyzer",
    "retry_or_fallback",
    "retry",
    "skip",
    "abort",
    "reporter",
    "planner",
    "select_tool",
]


def route_after_select(state: AgentState) -> Route:
    """Route to the step executor, analyzer, or terminal abort."""
    if state.get("abort_requested", False):
        return "abort"
    if state.get("current_step_index", 0) >= len(state.get("plan", [])):
        return "analyzer"
    return "execute_tool"


def route_after_execute(state: AgentState) -> Route:
    """Send successful tool execution to collection and failures to recovery."""
    return "collect" if state.get("last_tool_success", False) else "retry_or_fallback"


def route_after_retry_or_fallback(
    state: AgentState,
    *,
    max_retries: int = settings.max_tool_retries,
) -> Route:
    """Choose retry, noncritical skip, or critical abort from explicit state flags."""
    if state.get("abort_requested", False):
        return "abort"
    step_key = str(state.get("current_step_index", 0))
    retry_count = state.get("retry_counts", {}).get(step_key, 0)
    transient = state.get("last_error_type") == ToolTimeoutError.__name__
    if state.get("retry_requested", False) and transient and retry_count < max_retries:
        return "retry"
    if state.get("skip_requested", False):
        return "skip"
    return "abort"


def route_after_collect(state: AgentState) -> Route:
    """Continue the tool loop while planned steps remain."""
    if state.get("abort_requested", False):
        return "abort"
    if state.get("current_step_index", 0) < len(state.get("plan", [])):
        return "select_tool"
    return "analyzer"


def route_after_validation(
    state: AgentState,
    *,
    max_replans: int = settings.max_replans,
) -> Route:
    """Replan failed validation within the configured bound; otherwise report."""
    validation = state.get("validation")
    if validation is None or validation.passed:
        return "reporter"
    if state.get("replan_count", 0) < max_replans:
        return "planner"
    return "reporter"


def _bind_node(node: Any, deps: AgentDependencies) -> Any:
    """Bind dependencies through an async wrapper recognized by LangGraph."""

    async def invoke(state: AgentState) -> dict[str, Any]:
        return await instrumented_node(state, deps, node.__name__, node)

    return invoke


def build_graph(
    deps: AgentDependencies | None = None,
    *,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the complete stub research graph."""
    if deps is None:
        from app.agent.runner import build_default_dependencies

        deps = build_default_dependencies()

    workflow = StateGraph(AgentState)
    workflow.add_node("intake", _bind_node(intake, deps))
    workflow.add_node("planner", _bind_node(planner, deps))
    workflow.add_node("select_tool", _bind_node(select_tool, deps))
    workflow.add_node("execute_tool", _bind_node(execute_tool, deps))
    workflow.add_node("collect", _bind_node(collect, deps))
    workflow.add_node("retry_or_fallback", _bind_node(retry_or_fallback, deps))
    workflow.add_node("analyzer", _bind_node(analyzer, deps))
    workflow.add_node("validator", _bind_node(validator, deps))
    workflow.add_node("reporter", _bind_node(reporter, deps))

    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "planner")
    workflow.add_edge("planner", "select_tool")
    workflow.add_conditional_edges(
        "select_tool",
        route_after_select,
        {"execute_tool": "execute_tool", "analyzer": "analyzer", "abort": END},
    )
    workflow.add_conditional_edges(
        "execute_tool",
        route_after_execute,
        {"collect": "collect", "retry_or_fallback": "retry_or_fallback"},
    )
    workflow.add_conditional_edges(
        "retry_or_fallback",
        route_after_retry_or_fallback,
        {"retry": "execute_tool", "skip": "collect", "abort": END},
    )
    workflow.add_conditional_edges(
        "collect",
        route_after_collect,
        {"select_tool": "select_tool", "analyzer": "analyzer", "abort": END},
    )
    workflow.add_edge("analyzer", "validator")
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {"reporter": "reporter", "planner": "planner"},
    )
    workflow.add_edge("reporter", END)
    return workflow.compile(checkpointer=checkpointer or MemorySaver())
