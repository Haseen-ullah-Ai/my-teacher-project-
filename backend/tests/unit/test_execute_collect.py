"""Unit tests for real tool execution and result collection nodes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.agent.dependencies import AgentDependencies
from app.agent.models import PlanStep
from app.agent.nodes.collect import collect
from app.agent.nodes.execute_tool import execute_tool
from app.agent.state import AgentState
from app.tools.calculator import CalculatorTool
from app.tools.document_search import DocumentSearchTool
from app.tools.registry import ToolRegistry
from app.tools.schemas import DocumentSearchInput, DocumentSearchOutput


class NoopRunLogger:
    """Minimal run logger for node unit tests."""

    async def log_node(
        self,
        run_id: object,
        node: str,
        status: str,
        message: str,
    ) -> None:
        return None


class NoopLLMClient:
    """Unused LLM placeholder for dependency bundles in node tests."""

    async def generate_structured(self, *_: object, **__: object) -> Any:
        raise AssertionError("LLM must not be called in execute/collect tests")

    async def generate_text(self, *_: object, **__: object) -> Any:
        raise AssertionError("LLM must not be called in execute/collect tests")


def _base_state(**overrides: Any) -> AgentState:
    state: AgentState = {
        "run_id": uuid4(),
        "task": "test task",
        "plan": [],
        "current_step_index": 0,
        "tool_results": [],
        "memory": [],
        "errors": [],
        "retry_counts": {},
        "timestamps": {},
    }
    state.update(overrides)
    return state


def _deps(registry: ToolRegistry | None = None) -> AgentDependencies:
    return AgentDependencies(
        llm_client=NoopLLMClient(),
        tool_registry=registry or ToolRegistry(),
        session_factory=lambda: None,  # type: ignore[arg-type]
        run_logger=NoopRunLogger(),
    )


@pytest.mark.asyncio
async def test_execute_tool_runs_calculator_successfully() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    state = _base_state(
        plan=[
            PlanStep(
                index=0,
                description="Compute",
                tool_name="calculator",
                tool_args={"expression": "1 + 2"},
            )
        ],
    )

    update = await execute_tool(state, _deps(registry))

    assert update["last_tool_success"] is True
    assert update["last_error_type"] is None
    pending = update["pending_result"]
    assert pending["success"] is True
    assert pending["data"]["value"] == 3.0
    assert pending["duration_ms"] >= 0
    assert pending["metadata"]["tool_name"] == "calculator"
    assert update.get("errors", []) == []


@pytest.mark.asyncio
async def test_execute_tool_records_calculator_failure() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    state = _base_state(
        plan=[
            PlanStep(
                index=0,
                description="Invalid compute",
                tool_name="calculator",
                tool_args={"expression": "1 +"},
            )
        ],
    )

    update = await execute_tool(state, _deps(registry))

    assert update["last_tool_success"] is False
    assert update["last_error_type"] == "ToolInputError"
    pending = update["pending_result"]
    assert pending["success"] is False
    assert pending["error"] is not None
    assert update["skip_requested"] is True
    assert update["retry_requested"] is False
    assert len(update["errors"]) == 1


@pytest.mark.asyncio
async def test_execute_tool_handles_missing_registry_tool() -> None:
    state = _base_state(
        plan=[
            PlanStep(
                index=0,
                description="Missing tool",
                tool_name="missing_tool",
                tool_args={},
            )
        ],
    )

    update = await execute_tool(state, _deps(ToolRegistry()))

    assert update["last_tool_success"] is False
    assert update["last_error_type"] == "ToolNotFoundError"
    assert update["pending_result"]["success"] is False
    assert update["skip_requested"] is True


@pytest.mark.asyncio
async def test_collect_builds_execution_result_and_calculator_evidence() -> None:
    state = _base_state(
        pending_result={
            "tool_name": "calculator",
            "step_index": 0,
            "success": True,
            "data": {"value": 42.0, "normalized_expression": "6 * 7"},
            "error": None,
        },
    )

    update = await collect(state, _deps())

    assert len(update["tool_results"]) == 1
    result = update["tool_results"][0]
    assert result.success is True
    assert result.data["value"] == 42.0
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == "calculation"
    assert "6 * 7" in result.evidence[0].citation
    assert update["current_step_index"] == 1
    assert len(update["memory"]) == 1


@pytest.mark.asyncio
async def test_collect_preserves_failed_tool_result_without_fabricated_evidence() -> None:
    error_message = "Invalid input for calculator"
    state = _base_state(
        pending_result={
            "tool_name": "calculator",
            "step_index": 0,
            "success": False,
            "data": {},
            "error": error_message,
        },
    )

    update = await collect(state, _deps())

    result = update["tool_results"][0]
    assert result.success is False
    assert result.error == error_message
    assert result.evidence == []
    assert update["active_evidence"] == []


@pytest.mark.asyncio
async def test_execute_and_collect_document_search_evidence_shape() -> None:
    from uuid import uuid4 as make_uuid

    chunk_id = make_uuid()
    registry = ToolRegistry()

    class FixedDocumentSearchTool(DocumentSearchTool):
        async def run(self, input: DocumentSearchInput) -> DocumentSearchOutput:
            from app.tools.schemas import DocumentSearchResult

            return DocumentSearchOutput(
                results=[
                    DocumentSearchResult(
                        chunk_id=chunk_id,
                        document_title="Policy Handbook",
                        snippet="sample",
                        rank_score=0.9,
                        chunk_index=2,
                    )
                ]
            )

    registry.register(FixedDocumentSearchTool())
    state = _base_state(
        plan=[
            PlanStep(
                index=0,
                description="Search",
                tool_name="document_search",
                tool_args={"query": "policy", "top_k": 1},
            )
        ],
    )

    executed = await execute_tool(state, _deps(registry))
    collected = await collect({**state, **executed}, _deps())

    evidence = collected["tool_results"][0].evidence
    assert len(evidence) == 1
    assert evidence[0].source_id == str(chunk_id)
    assert "Policy Handbook" in evidence[0].citation
