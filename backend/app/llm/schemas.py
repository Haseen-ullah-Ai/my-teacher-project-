"""Structured contracts used by the planner, analyzer, and reporter."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.tools.schemas import ReportDraft, ReportEvidenceReference


class PlannedToolStep(BaseModel):
    """A single proposed call to one of the controlled local tools."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    tool_name: Literal["document_search", "csv_reader", "calculator", "report_generator"]
    tool_args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    """Ordered tool execution plan generated from the user task."""

    steps: list[PlannedToolStep] = Field(min_length=1, max_length=12)


class AnalysisFinding(BaseModel):
    """Evidence-backed statement derived from a successful tool result."""

    statement: str = Field(min_length=1)
    evidence_refs: list[ReportEvidenceReference] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    source_tool_call_ids: list[UUID] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Summary, findings, and recommendations produced by the analyzer."""

    summary: str = Field(min_length=1)
    findings: list[AnalysisFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReporterOutput(ReportDraft):
    """Reporter schema alias retained as a named LLM output contract."""
