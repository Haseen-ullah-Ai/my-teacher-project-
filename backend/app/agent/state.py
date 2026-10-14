"""Typed LangGraph state for a single ResearchPilot execution."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from app.agent.models import (
    Analysis,
    EvidenceRef,
    Finding,
    ParsedTask,
    PlanStep,
    ScratchFact,
    ToolExecutionResult,
    ValidationResult,
)
from app.tools.schemas import ReportDraft


class AgentState(TypedDict, total=False):
    """Mutable graph state; nodes return partial dictionaries for updates."""

    run_id: UUID
    task: str
    parsed_task: ParsedTask | None
    plan: list[PlanStep]
    current_step_index: int
    tool_results: list[ToolExecutionResult]
    findings: list[Finding]
    analysis: Analysis | None
    validation: ValidationResult | None
    report: ReportDraft | None
    errors: list[str]
    retry_counts: dict[str, int]
    replan_count: int
    status: str
    memory: list[ScratchFact]
    timestamps: dict[str, datetime]
    last_tool_success: bool
    last_error_type: str | None
    retry_requested: bool
    skip_requested: bool
    abort_requested: bool
    pending_result: dict[str, object]
    active_evidence: list[EvidenceRef]
    validation_feedback: list[str]
    completed: bool
    token_usage: dict[str, int]


ResearchState = AgentState
