"""Research run, execution, finding, validation, and report models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchRun(Base):
    """Top-level lifecycle record for a research task."""

    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'planning', 'running', 'analyzing', 'validating', "
            "'reporting', 'completed', 'failed', 'cancelled')",
            name="ck_research_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    plan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    final_report_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", use_alter=True, name="fk_research_runs_final_report_id"),
    )
    error: Mapped[str | None] = mapped_column(Text)
    replan_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    tool_call_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    token_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    llm_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="mock", server_default="mock"
    )

    steps: Mapped[list[PlanStep]] = relationship(back_populates="run", cascade="all, delete-orphan")
    tool_calls: Mapped[list[ToolCall]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    execution_logs: Mapped[list[ExecutionLog]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    validation_results: Mapped[list[ValidationResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="run", cascade="all, delete-orphan", foreign_keys="Report.run_id"
    )


class PlanStep(Base):
    """A single executable step in a run plan."""

    __tablename__ = "plan_steps"
    __table_args__ = (
        Index("ix_plan_steps_run_step", "run_id", "step_index", unique=True),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')",
            name="ck_plan_steps_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_args: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    depends_on: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))

    run: Mapped[ResearchRun] = relationship(back_populates="steps")
    tool_calls: Mapped[list[ToolCall]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )
    execution_logs: Mapped[list[ExecutionLog]] = relationship(back_populates="step")


class ToolCall(Base):
    """Persisted input, output, and timing for one tool attempt."""

    __tablename__ = "tool_calls"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_steps.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    run: Mapped[ResearchRun] = relationship(back_populates="tool_calls")
    step: Mapped[PlanStep] = relationship(back_populates="tool_calls")


class ExecutionLog(Base):
    """Structured record of a graph node or system event."""

    __tablename__ = "execution_logs"
    __table_args__ = (
        Index("ix_execution_logs_run_created_at", "run_id", "created_at"),
        CheckConstraint(
            "node IN ('intake', 'planner', 'executor', 'analyzer', 'validator', "
            "'reporter', 'system')",
            name="ck_execution_logs_node",
        ),
        CheckConstraint(
            "level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')",
            name="ck_execution_logs_level",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("plan_steps.id", ondelete="SET NULL")
    )
    node: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INFO", server_default="INFO"
    )
    event: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[ResearchRun] = relationship(back_populates="execution_logs")
    step: Mapped[PlanStep | None] = relationship(back_populates="execution_logs")


class Finding(Base):
    """A reportable statement and its evidence references."""

    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_findings_confidence"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_tool_call_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default=text("'{}'::uuid[]"),
    )

    run: Mapped[ResearchRun] = relationship(back_populates="findings")


class ValidationResult(Base):
    """Outcome and detailed checks for a validation attempt."""

    __tablename__ = "validation_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[ResearchRun] = relationship(back_populates="validation_results")


class Report(Base):
    """Structured final report for a research run."""

    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    file_paths: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[ResearchRun] = relationship(back_populates="reports", foreign_keys=[run_id])
