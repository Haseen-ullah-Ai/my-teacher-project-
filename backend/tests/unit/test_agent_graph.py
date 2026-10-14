"""Topology, routing, and persisted stub-run tests for the agent graph."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest

from app.agent.dependencies import AgentDependencies
from app.agent.graph import (
    build_graph,
    route_after_collect,
    route_after_execute,
    route_after_retry_or_fallback,
    route_after_select,
    route_after_validation,
)
from app.agent.models import ValidationResult
from app.agent.persistence import DatabaseRunLogger
from app.agent.runner import AgentRunner
from app.models.research import ExecutionLog, ResearchRun
from app.tools.document_search import DocumentSearchTool
from app.tools.registry import ToolRegistry, build_default_registry
from app.tools.schemas import DocumentSearchInput, DocumentSearchOutput


class MemoryDatabase:
    """Minimal shared database for testing asynchronous run persistence."""

    def __init__(self) -> None:
        self.run: ResearchRun | None = None
        self.logs: list[ExecutionLog] = []


class MemorySession:
    """Async-session-shaped test double consumed by AgentRunner and logger."""

    def __init__(self, database: MemoryDatabase) -> None:
        self.database = database

    async def __aenter__(self) -> MemorySession:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def add(self, item: object) -> None:
        if isinstance(item, ResearchRun):
            self.database.run = item
        elif isinstance(item, ExecutionLog):
            self.database.logs.append(item)

    async def get(self, model: type[Any], key: UUID) -> Any:
        if model is ResearchRun and self.database.run is not None:
            if self.database.run.id == key:
                return self.database.run
        return None

    async def commit(self) -> None:
        return None


class NoopLLMClient:
    """Protocol-compatible unused model for stub-only graph execution."""

    async def generate_structured(self, *_: object, **__: object) -> Any:
        raise AssertionError("Stage 6 stub nodes must not call the LLM")

    async def generate_text(self, *_: object, **__: object) -> Any:
        raise AssertionError("Stage 6 stub nodes must not call the LLM")


class EmptyDocumentSearchTool(DocumentSearchTool):
    """Graph test double that succeeds without a database session."""

    async def run(self, input: DocumentSearchInput) -> DocumentSearchOutput:
        return DocumentSearchOutput(results=[])


def build_graph_test_registry() -> ToolRegistry:
    """Registry used by end-to-end graph tests without external services."""
    registry = ToolRegistry()
    registry.register(EmptyDocumentSearchTool())
    return registry


class BlockingRunLogger:
    """Pause the first node so cancellation behavior can be tested deterministically."""

    def __init__(self, session_factory: Any) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.database_logger = DatabaseRunLogger(session_factory)

    async def log_node(
        self,
        run_id: object,
        node: str,
        status: str,
        message: str,
    ) -> None:
        self.entered.set()
        await self.release.wait()
        await self.database_logger.log_node(run_id, node, status, message)


@pytest.mark.asyncio
async def test_graph_has_required_nodes_and_direct_edges() -> None:
    """Compiled graph contains the full Stage 6 node topology."""
    graph = build_graph()
    topology = graph.get_graph()
    node_names = set(topology.nodes)
    edge_pairs = {(edge.source, edge.target) for edge in topology.edges}

    assert {
        "intake",
        "planner",
        "select_tool",
        "execute_tool",
        "collect",
        "retry_or_fallback",
        "analyzer",
        "validator",
        "reporter",
    } <= node_names
    assert ("intake", "planner") in edge_pairs
    assert ("planner", "select_tool") in edge_pairs
    assert ("analyzer", "validator") in edge_pairs
    assert ("reporter", "__end__") in edge_pairs
    assert "graph TD" in topology.draw_mermaid()


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"plan": [], "current_step_index": 0}, "analyzer"),
        ({"plan": [{"index": 0}], "current_step_index": 0}, "execute_tool"),
        ({"plan": [{"index": 0}], "current_step_index": 0, "abort_requested": True}, "abort"),
    ],
)
def test_select_route_table(state: dict[str, Any], expected: str) -> None:
    """Selection routing handles remaining work, completion, and abort."""
    assert route_after_select(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"last_tool_success": True}, "collect"),
        ({"last_tool_success": False}, "retry_or_fallback"),
    ],
)
def test_execute_route_table(state: dict[str, Any], expected: str) -> None:
    """Executor routes successful and failed attempts to the correct node."""
    assert route_after_execute(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            {
                "last_error_type": "ToolTimeoutError",
                "retry_requested": True,
                "retry_counts": {"0": 0},
            },
            "retry",
        ),
        (
            {
                "last_error_type": "ToolInputError",
                "retry_requested": True,
                "retry_counts": {"0": 0},
                "skip_requested": True,
            },
            "skip",
        ),
        (
            {
                "last_error_type": "ToolTimeoutError",
                "retry_requested": True,
                "retry_counts": {"0": 3},
                "skip_requested": True,
            },
            "skip",
        ),
        ({"abort_requested": True, "skip_requested": True}, "abort"),
        ({"last_error_type": "ToolExecutionError"}, "abort"),
    ],
)
def test_recovery_route_table(state: dict[str, Any], expected: str) -> None:
    """Recovery routing distinguishes transient retry, skip, and abort cases."""
    assert route_after_retry_or_fallback(state, max_retries=3) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"current_step_index": 0, "plan": [{"index": 0}]}, "select_tool"),
        ({"current_step_index": 1, "plan": [{"index": 0}]}, "analyzer"),
        ({"current_step_index": 1, "plan": [], "abort_requested": True}, "abort"),
    ],
)
def test_collect_route_table(state: dict[str, Any], expected: str) -> None:
    """Collection routes to the next step, analyzer, or terminal abort."""
    assert route_after_collect(state) == expected


@pytest.mark.parametrize(
    ("validation", "replan_count", "max_replans", "expected"),
    [
        (ValidationResult(passed=True), 0, 2, "reporter"),
        (ValidationResult(passed=False), 0, 2, "planner"),
        (ValidationResult(passed=False), 2, 2, "reporter"),
        (None, 0, 2, "reporter"),
    ],
)
def test_validation_route_table(
    validation: ValidationResult | None,
    replan_count: int,
    max_replans: int,
    expected: str,
) -> None:
    """Validation routing reports passing/exhausted results and bounds replans."""
    assert (
        route_after_validation(
            {"validation": validation, "replan_count": replan_count},
            max_replans=max_replans,
        )
        == expected
    )


@pytest.mark.asyncio
async def test_runner_completes_stub_run_and_persists_node_logs() -> None:
    """A complete graph run transitions pending to completed and records each node."""
    database = MemoryDatabase()

    def session_factory() -> MemorySession:
        return MemorySession(database)

    logger = DatabaseRunLogger(session_factory)
    dependencies = AgentDependencies(
        llm_client=NoopLLMClient(),
        tool_registry=build_graph_test_registry(),
        session_factory=session_factory,
        run_logger=logger,
    )
    runner = AgentRunner(session_factory, deps=dependencies)

    run_id = await runner.run("Analyze Q3 revenue")
    state = await runner.wait(run_id)
    events = [event async for event in runner.stream_events(run_id)]

    assert state["status"] == "completed"
    assert state["completed"] is True
    assert database.run is not None
    assert database.run.id == run_id
    assert database.run.status == "completed"
    assert [log.node for log in database.logs] == [
        "intake",
        "planner",
        "executor",
        "executor",
        "executor",
        "analyzer",
        "validator",
        "reporter",
        "reporter",
    ]
    assert [event["node"] for event in events] == [
        "intake",
        "planner",
        "select_tool",
        "execute_tool",
        "collect",
        "analyzer",
        "validator",
        "reporter",
    ]
    assert state["report"].title == "ResearchPilot Stub Report"
    with pytest.raises(ValueError, match="already terminal"):
        await runner.resume(run_id)


@pytest.mark.asyncio
async def test_runner_cancellation_is_persisted() -> None:
    """Cancelling a blocked node persists the run as cancelled."""
    database = MemoryDatabase()

    def session_factory() -> MemorySession:
        return MemorySession(database)

    blocker = BlockingRunLogger(session_factory)
    dependencies = AgentDependencies(
        llm_client=NoopLLMClient(),
        tool_registry=build_graph_test_registry(),
        session_factory=session_factory,
        run_logger=blocker,
    )
    runner = AgentRunner(session_factory, deps=dependencies)

    run_id = await runner.run("Cancelable stub run")
    await blocker.entered.wait()
    await runner.cancel(run_id)

    assert database.run is not None
    assert database.run.status == "cancelled"
    assert database.run.error == "Research run was cancelled."
    events = [event async for event in runner.stream_events(run_id)]
    assert events[-1]["status"] == "cancelled"

    blocker.release.set()
    await runner.resume(run_id)
    resumed_state = await runner.wait(run_id)
    assert resumed_state["status"] == "completed"
    assert database.run.status == "completed"
    assert any(log.event == "run_resumed" for log in database.logs)


@pytest.mark.asyncio
async def test_graph_mermaid_export_writes_docs_file(tmp_path: Any) -> None:
    """The graph export helper writes Mermaid source from the compiled graph."""
    from app.agent.export_graph import export_graph

    path = export_graph(tmp_path / "agent_graph.mmd")

    assert path.is_file()
    assert "retry_or_fallback" in path.read_text(encoding="utf-8")
