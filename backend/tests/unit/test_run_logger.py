"""Run logger persistence, redaction, metric, and request-correlation tests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from structlog.contextvars import bind_contextvars, unbind_contextvars

from app.agent.dependencies import AgentDependencies
from app.agent.nodes.common import instrumented_node
from app.agent.persistence import DatabaseRunLogger
from app.agent.runner import AgentRunner
from app.agent.state import AgentState
from app.main import create_app
from app.models.research import ExecutionLog, ResearchRun
from app.services.metrics import (
    render_metrics,
    retries_total,
    run_duration_seconds,
    runs_total,
    tool_calls_total,
)
from app.services.run_logger import REDACTED, RunLogger
from app.tools.registry import build_default_registry


class MemoryDatabase:
    """Stores minimal ORM rows written by fake async sessions."""

    def __init__(self) -> None:
        self.run: ResearchRun | None = None
        self.logs: list[ExecutionLog] = []


class MemorySession:
    """Async database-session stand-in for execution log tests."""

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

    def add_all(self, items: list[object]) -> None:
        for item in items:
            self.add(item)

    async def get(self, model: type[Any], key: object) -> Any:
        if model is ResearchRun and self.database.run is not None:
            if self.database.run.id == key:
                return self.database.run
        return None

    async def commit(self) -> None:
        return None


class NoopLLMClient:
    """Protocol implementation proving stub nodes don't need a model."""

    async def generate_structured(self, *_: object, **__: object) -> Any:
        raise AssertionError("Stub graph called the LLM")

    async def generate_text(self, *_: object, **__: object) -> Any:
        raise AssertionError("Stub graph called the LLM")


@pytest.mark.asyncio
async def test_node_failure_flushes_boundary_and_failure_logs() -> None:
    """A failing node flushes its start and failure records before propagating."""
    database = MemoryDatabase()
    run_id = uuid4()
    database.run = ResearchRun(id=run_id, task="failure test", status="pending")
    logger = RunLogger(run_id, lambda: MemorySession(database), batch_size=100)
    dependencies = AgentDependencies(
        llm_client=NoopLLMClient(),
        tool_registry=build_default_registry(),
        session_factory=lambda: MemorySession(database),
        run_logger=logger,
    )
    state: AgentState = {"run_id": run_id, "timestamps": {}}

    async def fail_node(_state: AgentState, _deps: AgentDependencies) -> dict[str, Any]:
        raise RuntimeError("deliberate test failure")

    with pytest.raises(RuntimeError, match="deliberate"):
        await instrumented_node(state, dependencies, "planner", fail_node)

    assert [entry.event for entry in database.logs] == ["node_started", "node_failed"]
    assert database.logs[-1].data["error"] == "deliberate test failure"


@pytest.mark.asyncio
async def test_run_logger_flushes_redacted_logs_in_event_order() -> None:
    """Buffered logs persist in order and sensitive fields are redacted."""
    database = MemoryDatabase()
    run_id = uuid4()
    database.run = ResearchRun(id=run_id, task="test run", status="pending")
    logger = RunLogger(run_id, lambda: MemorySession(database), batch_size=100)

    await logger.info(
        "planner",
        "node_started",
        "Planning started.",
        api_key="sk-1234567890abcdefghijkl",
        nested={"password": "secret", "safe": "value"},
        prompt_tokens=42,
    )
    await logger.warn("planner", "retry_scheduled", "Retry queued.", access_token="abc")
    await logger.shutdown()

    assert [record.event for record in database.logs] == [
        "node_started",
        "retry_scheduled",
    ]
    first_data = database.logs[0].data
    assert first_data["api_key"] == REDACTED
    assert first_data["nested"]["password"] == REDACTED
    assert first_data["nested"]["safe"] == "value"
    assert first_data["prompt_tokens"] == 42
    assert database.logs[1].data["access_token"] == REDACTED


@pytest.mark.asyncio
async def test_run_logger_persists_request_correlation_id() -> None:
    """Request context is copied into persisted execution-log data."""
    database = MemoryDatabase()
    run_id = uuid4()
    database.run = ResearchRun(id=run_id, task="correlation", status="running")
    logger = RunLogger(run_id, lambda: MemorySession(database))
    bind_contextvars(request_id="request-test-42")
    try:
        await logger.info("planner", "node_started", "Planning started.")
        await logger.flush()
    finally:
        unbind_contextvars("request_id")

    assert database.logs[0].data["request_id"] == "request-test-42"


@pytest.mark.asyncio
async def test_llm_call_log_keeps_hash_and_usage_without_prompt_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM logs expose prompt hash and token counts without raw prompt by default."""
    import hashlib

    from app.core.config import settings

    monkeypatch.setattr(settings, "log_llm_prompts", False)
    database = MemoryDatabase()
    run_id = uuid4()
    database.run = ResearchRun(id=run_id, task="llm logging", status="running")
    logger = RunLogger(run_id, lambda: MemorySession(database))
    prompt = "Sensitive prompt content"

    await logger.llm_call(
        "planner",
        provider="mock",
        model="test-model",
        prompt=prompt,
        latency_ms=12,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    await logger.flush()

    logged_data = database.logs[0].data
    assert logged_data["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert logged_data["prompt_tokens"] == 10
    assert "prompt" not in logged_data


@pytest.mark.asyncio
async def test_run_logger_flushes_pending_logs_after_failed_run() -> None:
    """Failure state and buffered diagnostic events survive explicit shutdown."""
    database = MemoryDatabase()
    run_id = uuid4()
    database.run = ResearchRun(id=run_id, task="will fail", status="running")
    logger = RunLogger(run_id, lambda: MemorySession(database), batch_size=100)

    await logger.error("planner", "node_failed", "Planner failed.", reason="invalid plan")
    await logger.set_status("failed")
    await logger.shutdown()

    assert database.run.status == "failed"
    assert database.run.finished_at is not None
    assert len(database.logs) == 1
    assert database.logs[0].event == "node_failed"
    assert database.logs[0].data == {"reason": "invalid plan"}


@pytest.mark.asyncio
async def test_runner_increments_prometheus_run_and_tool_metrics() -> None:
    """A completed stub execution updates labeled counters and histograms."""
    from app.services.metrics import tool_duration_seconds

    database = MemoryDatabase()
    before_run = runs_total.labels(status="completed")._value.get()
    before_tool = tool_calls_total.labels(tool="document_search", status="succeeded")._value.get()
    before_retries = retries_total._value.get()
    before_duration = tool_duration_seconds.labels(tool="document_search")._sum.get()
    before_run_duration = run_duration_seconds._sum.get()

    def session_factory() -> MemorySession:
        return MemorySession(database)

    database_logger = DatabaseRunLogger(session_factory)
    dependencies = AgentDependencies(
        llm_client=NoopLLMClient(),
        tool_registry=build_default_registry(),
        session_factory=session_factory,
        run_logger=database_logger,
    )
    runner = AgentRunner(session_factory, deps=dependencies)
    run_id = await runner.run("Q3 revenue")
    result = await runner.wait(run_id)

    assert result["status"] == "completed"
    assert runs_total.labels(status="completed")._value.get() == before_run + 1
    assert (
        tool_calls_total.labels(tool="document_search", status="succeeded")._value.get()
        == before_tool + 1
    )
    assert retries_total._value.get() == before_retries
    assert tool_duration_seconds.labels(tool="document_search")._sum.get() == before_duration
    assert run_duration_seconds._sum.get() >= before_run_duration
    output, content_type = render_metrics()
    assert b"researchpilot_runs_total" in output
    assert "text/plain" in content_type


@pytest.mark.asyncio
async def test_default_runner_persists_full_node_event_story() -> None:
    """The production logger persists ordered node boundaries and tool events."""
    database = MemoryDatabase()

    def session_factory() -> MemorySession:
        return MemorySession(database)

    runner = AgentRunner(session_factory)
    run_id = await runner.run("Analyze regional sales")
    final_state = await runner.wait(run_id)

    event_names = [entry.event for entry in database.logs]
    assert final_state["status"] == "completed"
    assert event_names[0:3] == ["node_started", "node_transition", "node_finished"]
    assert "tool_call_started" in event_names
    assert "tool_call_finished" in event_names
    assert "validation_check" in event_names
    assert "run_completed" in event_names
    assert event_names[-1] == "node_finished"
    assert database.run is not None
    assert database.run.tool_call_count == 1


def test_request_middleware_echoes_and_logs_request_id() -> None:
    """Correlation ID middleware preserves caller IDs and emits them in response."""
    client = TestClient(create_app())
    response = client.get("/health", headers={"X-Request-ID": "request-test-42"})

    assert response.headers["X-Request-ID"] == "request-test-42"
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert b"researchpilot_runs_total" in metrics_response.content


def test_run_summary_serializes_persisted_execution_counters() -> None:
    """The RunSummary response model exposes all run counters."""
    from app.schemas.metrics import RunSummary

    run = ResearchRun(
        id=uuid4(),
        task="metrics",
        status="completed",
        total_duration_ms=125,
        tool_call_count=4,
        retry_count=1,
        failure_count=1,
        token_count=512,
        replan_count=0,
    )

    summary = RunSummary.from_run(run)

    assert summary.tool_call_count == 4
    assert summary.retry_count == 1
    assert summary.failure_count == 1
    assert summary.token_count == 512
    assert summary.total_duration_ms == 125
