"""Pydantic read and create schemas for persisted database records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.research import Evidence


class ORMReadModel(BaseModel):
    """Base schema configured for SQLAlchemy model serialization."""

    model_config = ConfigDict(from_attributes=True)


class ResearchRunCreate(BaseModel):
    """Create payload for a research run."""

    task: str
    llm_provider: str = "mock"


class ResearchRunRead(ORMReadModel):
    """Read model for a research run."""

    id: UUID
    task: str
    status: Literal[
        "pending",
        "planning",
        "running",
        "analyzing",
        "validating",
        "reporting",
        "completed",
        "failed",
        "cancelled",
    ]
    plan: list[dict[str, Any]] | None
    final_report_id: UUID | None
    error: str | None
    replan_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    total_duration_ms: int | None
    llm_provider: str


class PlanStepCreate(BaseModel):
    """Create payload for a plan step."""

    run_id: UUID
    step_index: int
    description: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "running", "succeeded", "failed", "skipped"] = "pending"
    retries: int = 0
    depends_on: list[int] | None = None


class PlanStepRead(ORMReadModel, PlanStepCreate):
    """Read model for a plan step."""

    id: UUID


class ToolCallCreate(BaseModel):
    """Create payload for a tool call."""

    run_id: UUID
    step_id: UUID
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    status: str
    error_type: str | None = None
    error_message: str | None = None
    attempt: int = 1
    duration_ms: int | None = None


class ToolCallRead(ORMReadModel, ToolCallCreate):
    """Read model for a tool call."""

    id: UUID
    started_at: datetime


class ExecutionLogCreate(BaseModel):
    """Create payload for an execution log."""

    run_id: UUID
    step_id: UUID | None = None
    node: Literal["intake", "planner", "executor", "analyzer", "validator", "reporter", "system"]
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    event: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class ExecutionLogRead(ORMReadModel, ExecutionLogCreate):
    """Read model for an execution log."""

    id: int
    created_at: datetime


class FindingCreate(BaseModel):
    """Create payload for an analyzed finding."""

    run_id: UUID
    statement: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    source_tool_call_ids: list[UUID] = Field(default_factory=list)


class FindingRead(ORMReadModel, FindingCreate):
    """Read model for a finding."""

    id: UUID


class ValidationCheck(BaseModel):
    """One named validation check and its outcome."""

    name: str
    passed: bool
    detail: str = ""


class ValidationResultCreate(BaseModel):
    """Create payload for a validation result."""

    run_id: UUID
    attempt: int
    passed: bool
    checks: list[ValidationCheck]


class ValidationResultRead(ORMReadModel, ValidationResultCreate):
    """Read model for a validation result."""

    id: UUID
    created_at: datetime


class ReportCreate(BaseModel):
    """Create payload for a generated report."""

    run_id: UUID
    title: str
    summary: str
    content_json: dict[str, Any]
    content_markdown: str
    file_paths: list[str] = Field(default_factory=list)


class ReportRead(ORMReadModel, ReportCreate):
    """Read model for a report."""

    id: UUID
    created_at: datetime
