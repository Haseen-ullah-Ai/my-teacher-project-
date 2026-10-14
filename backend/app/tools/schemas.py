"""Validated request and response models for controlled tools."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base tool schema rejecting unknown planner-supplied fields."""

    model_config = ConfigDict(extra="forbid")


class DocumentSearchInput(StrictModel):
    """PostgreSQL document search request."""

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    document_filter: str | None = Field(default=None, min_length=1, max_length=500)


class DocumentSearchResult(BaseModel):
    """One ranked search result."""

    chunk_id: UUID
    document_title: str
    snippet: str
    rank_score: float
    chunk_index: int


class DocumentSearchOutput(BaseModel):
    """Search results; an empty list is a successful result."""

    results: list[DocumentSearchResult]


class CSVReaderInput(StrictModel):
    """Registered-dataset operation request."""

    operation: Literal["describe", "head", "filter", "aggregate", "top_n"]
    filename: str = Field(min_length=1, max_length=500)
    n: int = Field(default=10, ge=1, le=200)
    column: str | None = None
    operator: Literal["eq", "ne", "gt", "lt", "gte", "lte", "in", "contains"] | None = None
    value: Any = None
    group_by: list[str] = Field(default_factory=list, max_length=10)
    metric_column: str | None = None
    agg: Literal["sum", "mean", "min", "max", "count", "median"] | None = None
    ascending: bool = False

    @model_validator(mode="after")
    def validate_operation_fields(self) -> CSVReaderInput:
        """Require operation-specific fields before touching the database."""
        if self.operation == "filter":
            if not self.column or self.operator is None:
                raise ValueError("filter requires column and operator")
            if self.operator == "in" and not isinstance(self.value, list):
                raise ValueError("filter operator 'in' requires a list value")
            if self.operator != "in" and self.value is None:
                raise ValueError("filter requires a non-null value")
        elif self.operation == "aggregate":
            if self.agg is None:
                raise ValueError("aggregate requires agg")
            if self.agg != "count" and not self.metric_column:
                raise ValueError("aggregate requires metric_column unless agg is count")
        elif self.operation == "top_n" and not self.column:
            raise ValueError("top_n requires column")
        return self


class CSVReaderOutput(BaseModel):
    """CSV operation result with bounded rows and reproducible provenance."""

    operation: str
    result: Any
    provenance: dict[str, Any]


class CalculatorInput(StrictModel):
    """Safe arithmetic expression request."""

    expression: str = Field(min_length=1, max_length=1000)


class CalculatorOutput(BaseModel):
    """Calculated numeric value and normalized source expression."""

    value: int | float
    normalized_expression: str


class ReportEvidenceReference(StrictModel):
    """Evidence reference attached to a report section or finding."""

    reference: str = Field(min_length=1)
    citation: str = Field(min_length=1)


class ReportSection(StrictModel):
    """Narrative report section with supporting evidence references."""

    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)
    evidence_refs: list[ReportEvidenceReference] = Field(default_factory=list)


class ReportFinding(StrictModel):
    """Finding to be rendered in the report."""

    statement: str = Field(min_length=1)
    evidence_refs: list[ReportEvidenceReference] = Field(default_factory=list)


class AppendixTable(StrictModel):
    """Simple tabular appendix data."""

    title: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    rows: list[list[Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_row_widths(self) -> AppendixTable:
        """Require every table row to match the declared column count."""
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Every appendix row must match the declared column count")
        return self


class ReportDraft(StrictModel):
    """Structured draft passed to Markdown and PDF rendering."""

    title: str = Field(min_length=1, max_length=300)
    executive_summary: str = Field(min_length=1)
    sections: list[ReportSection]
    findings: list[ReportFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    appendix_tables: list[AppendixTable] = Field(default_factory=list)


class ReportGeneratorOutput(BaseModel):
    """Rendered report artifacts."""

    markdown: str
    markdown_path: str
    pdf_path: str
