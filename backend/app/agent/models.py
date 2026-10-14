"""Typed data structures carried through the research-agent graph."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.tools.schemas import ReportDraft


class ParsedTask(BaseModel):
    """Normalized request fields extracted during task intake."""

    objective: str
    entities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """A single planned local tool operation."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    description: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)
    status: Literal["pending", "running", "succeeded", "failed", "skipped"] = "pending"


class EvidenceRef(BaseModel):
    """A citation to a persisted tool call or source record."""

    evidence_id: str
    source_type: str
    source_id: str
    citation: str


class Finding(BaseModel):
    """Evidence-backed statement collected during analysis."""

    statement: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


class Analysis(BaseModel):
    """High-level analysis summary and structured findings."""

    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    """One named validation check."""

    name: str
    passed: bool
    detail: str = ""


class ValidationResult(BaseModel):
    """Result of validating an analysis and proposed report."""

    passed: bool
    checks: list[ValidationCheck] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)


class ToolExecutionResult(BaseModel):
    """Tool output and execution metadata carried in graph state."""

    tool_name: str
    step_index: int
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ScratchFact(BaseModel):
    """A compact fact in short-term agent memory and its source references."""

    key: str
    value: Any
    source_refs: list[EvidenceRef] = Field(default_factory=list)


class AgentStateModel(BaseModel):
    """Pydantic counterpart for validating serialized graph state."""

    run_id: UUID
    task: str
    parsed_task: ParsedTask | None = None
    plan: list[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    analysis: Analysis | None = None
    validation: ValidationResult | None = None
    report: ReportDraft | None = None
    errors: list[str] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    replan_count: int = 0
    status: str = "pending"
    memory: list[ScratchFact] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
