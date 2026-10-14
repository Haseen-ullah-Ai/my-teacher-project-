"""Repositories for research execution aggregates."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import (
    ExecutionLog,
    Finding,
    PlanStep,
    Report,
    ResearchRun,
    ToolCall,
    ValidationResult,
)
from app.schemas.database import (
    ExecutionLogCreate,
    FindingCreate,
    PlanStepCreate,
    ReportCreate,
    ToolCallCreate,
    ValidationResultCreate,
)


class ResearchRunRepository:
    """Data access for research runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, task: str, llm_provider: str = "mock") -> ResearchRun:
        """Create and flush a pending research run."""
        run = ResearchRun(task=task, llm_provider=llm_provider)
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: UUID) -> ResearchRun | None:
        """Return a run by its identifier."""
        return await self.session.get(ResearchRun, run_id)

    async def list_recent(self, limit: int = 50) -> Sequence[ResearchRun]:
        """Return newest runs, bounded by a requested limit."""
        result = await self.session.scalars(
            select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(limit)
        )
        return result.all()


class PlanStepRepository:
    """Data access for ordered plan steps."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: PlanStepCreate) -> PlanStep:
        """Create a plan step for a run."""
        step = PlanStep(**payload.model_dump())
        self.session.add(step)
        await self.session.flush()
        return step

    async def list_for_run(self, run_id: UUID) -> Sequence[PlanStep]:
        """Return plan steps in execution order."""
        result = await self.session.scalars(
            select(PlanStep).where(PlanStep.run_id == run_id).order_by(PlanStep.step_index)
        )
        return result.all()


class ToolCallRepository:
    """Data access for tool call attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ToolCallCreate) -> ToolCall:
        """Create a tool call attempt."""
        call = ToolCall(**payload.model_dump())
        self.session.add(call)
        await self.session.flush()
        return call

    async def list_for_run(self, run_id: UUID) -> Sequence[ToolCall]:
        """Return tool calls for a run in start-time order."""
        result = await self.session.scalars(
            select(ToolCall).where(ToolCall.run_id == run_id).order_by(ToolCall.started_at)
        )
        return result.all()


class ExecutionLogRepository:
    """Data access for ordered execution events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ExecutionLogCreate) -> ExecutionLog:
        """Create an execution log event."""
        log = ExecutionLog(**payload.model_dump())
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_for_run(self, run_id: UUID, limit: int = 500) -> Sequence[ExecutionLog]:
        """Return the latest execution logs in chronological order."""
        result = await self.session.scalars(
            select(ExecutionLog)
            .where(ExecutionLog.run_id == run_id)
            .order_by(ExecutionLog.created_at, ExecutionLog.id)
            .limit(limit)
        )
        return result.all()


class FindingRepository:
    """Data access for analyzer findings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: FindingCreate) -> Finding:
        """Create a finding record."""
        finding = Finding(**payload.model_dump())
        self.session.add(finding)
        await self.session.flush()
        return finding

    async def list_for_run(self, run_id: UUID) -> Sequence[Finding]:
        """Return findings for a run."""
        result = await self.session.scalars(select(Finding).where(Finding.run_id == run_id))
        return result.all()


class ValidationResultRepository:
    """Data access for validation attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ValidationResultCreate) -> ValidationResult:
        """Create a validation result."""
        validation = ValidationResult(**payload.model_dump())
        self.session.add(validation)
        await self.session.flush()
        return validation

    async def list_for_run(self, run_id: UUID) -> Sequence[ValidationResult]:
        """Return validation attempts in attempt order."""
        result = await self.session.scalars(
            select(ValidationResult)
            .where(ValidationResult.run_id == run_id)
            .order_by(ValidationResult.attempt)
        )
        return result.all()


class ReportRepository:
    """Data access for generated reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ReportCreate) -> Report:
        """Create a report linked to its research run."""
        report = Report(**payload.model_dump())
        self.session.add(report)
        await self.session.flush()
        return report

    async def get(self, report_id: UUID) -> Report | None:
        """Return a report by its identifier."""
        return await self.session.get(Report, report_id)

    async def list_for_run(self, run_id: UUID) -> Sequence[Report]:
        """Return reports for a run in creation order."""
        result = await self.session.scalars(
            select(Report).where(Report.run_id == run_id).order_by(Report.created_at)
        )
        return result.all()
