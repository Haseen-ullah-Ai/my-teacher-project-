"""Public summaries of persisted run metrics."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunSummary(BaseModel):
    """Compact run lifecycle and execution metrics."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    status: str
    total_duration_ms: int | None = None
    tool_call_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    token_count: int = Field(ge=0)
    replan_count: int = Field(ge=0)

    @classmethod
    def from_run(cls, run: object) -> RunSummary:
        """Build a public run summary from its persisted ORM row."""
        return cls(
            run_id=getattr(run, "id"),
            status=getattr(run, "status"),
            total_duration_ms=getattr(run, "total_duration_ms"),
            tool_call_count=getattr(run, "tool_call_count"),
            retry_count=getattr(run, "retry_count"),
            failure_count=getattr(run, "failure_count"),
            token_count=getattr(run, "token_count"),
            replan_count=getattr(run, "replan_count"),
        )
