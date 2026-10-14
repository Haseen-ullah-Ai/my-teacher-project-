"""Service that coordinates the research workflow."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.agent.models import Analysis
from app.schemas.research import Evidence, ResearchReport, TaskRequest


class ResearchService:
    """Thin service bound to the execution graph and database access."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.graph = build_graph()

    async def run_task(self, payload: TaskRequest) -> ResearchReport:
        """Execute a task through the current graph and return a report."""
        if not payload.task.strip():
            raise ValueError("Task cannot be empty")

        state = await self.graph.ainvoke(
            {"task": payload.task},
            config={
                "configurable": {
                    "thread_id": str(uuid4()),
                }
            },
        )

        analysis = state.get("analysis")
        if not isinstance(analysis, Analysis):
            raise RuntimeError(
                "Research graph completed without a structured analysis"
            )

        # Deduplicate evidence across findings while preserving its order.
        unique_evidence: dict[tuple[str, str], Evidence] = {}

        for finding in analysis.findings:
            for item in finding.evidence:
                key = (item.source_type, item.source_id)

                if key not in unique_evidence:
                    unique_evidence[key] = Evidence(
                        source_type=item.source_type,
                        source_id=item.source_id,
                        citation=item.citation,
                    )

        return ResearchReport(
            task=payload.task,
            summary=analysis.summary,
            findings=[finding.statement for finding in analysis.findings],
            recommendations=analysis.recommendations,
            evidence=list(unique_evidence.values()),
        )
