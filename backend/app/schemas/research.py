"""Schemas for research tasks, tool contracts, and report output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Incoming research task payload."""

    task: str = Field(..., min_length=5, description="User request in natural language")
    context: dict[str, Any] = Field(default_factory=dict, description="Optional execution context")


class ToolDefinition(BaseModel):
    """Describes a callable local tool."""

    name: str
    description: str
    timeout_seconds: int = 30


class Evidence(BaseModel):
    """Evidence object used in a final report."""

    source_type: str
    source_id: str
    citation: str


class ToolResult(BaseModel):
    """Result produced by a local tool call."""

    tool_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Structured report returned to the frontend."""

    task: str
    summary: str
    findings: list[str]
    recommendations: list[str]
    evidence: list[Evidence] = Field(default_factory=list)
