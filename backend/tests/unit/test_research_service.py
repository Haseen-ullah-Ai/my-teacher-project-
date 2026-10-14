"""Research service tests for configured async graph execution and response mapping."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.agent.models import Analysis, EvidenceRef, Finding
from app.schemas.research import TaskRequest
from app.services.research_service import ResearchService


class CapturingGraph:
    """Async graph double that records invocation arguments."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.inputs: list[dict[str, Any]] = []
        self.configs: list[dict[str, Any]] = []

    async def ainvoke(
        self,
        input: dict[str, Any],
        *,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Record an async graph call and return its structured state."""
        self.inputs.append(input)
        self.configs.append(config)
        return self.result


@pytest.mark.asyncio
async def test_research_service_uses_async_thread_config_and_graph_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use a checkpoint thread id and map graph analysis without canned claims."""
    task = "Research local AI documents"
    analysis = Analysis(
        summary="Analysis generated from collected sources.",
        findings=[
            Finding(
                statement="A sourced finding.",
                evidence=[
                    EvidenceRef(
                        evidence_id="tc:123",
                        source_type="tool_call",
                        source_id="123",
                        citation="Local source, row 1",
                    )
                ],
                confidence=0.9,
            )
        ],
        recommendations=["Review the cited source."],
    )
    graph = CapturingGraph({"analysis": analysis})
    monkeypatch.setattr("app.services.research_service.build_graph", lambda: graph)
    service = ResearchService()

    report = await service.run_task(TaskRequest(task=task))

    assert graph.inputs == [{"task": task}]
    configurable = graph.configs[0]["configurable"]
    assert isinstance(configurable, dict)
    UUID(str(configurable["thread_id"]))
    assert report.task == task
    assert report.summary == analysis.summary
    assert report.findings == ["A sourced finding."]
    assert report.recommendations == ["Review the cited source."]
    assert [item.model_dump() for item in report.evidence] == [
        {
            "source_type": "tool_call",
            "source_id": "123",
            "citation": "Local source, row 1",
        }
    ]


@pytest.mark.asyncio
async def test_research_service_rejects_missing_graph_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail explicitly instead of fabricating a successful research response."""
    graph = CapturingGraph({})
    monkeypatch.setattr("app.services.research_service.build_graph", lambda: graph)
    service = ResearchService()

    with pytest.raises(RuntimeError, match="without a structured analysis"):
        await service.run_task(TaskRequest(task="Research local AI documents"))
