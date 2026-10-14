"""Database-backed run transition logging for agent nodes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.models.research import ExecutionLog, ResearchRun

_LOG_NODE_ALIASES = {
    "select_tool": "executor",
    "execute_tool": "executor",
    "collect": "executor",
    "retry_or_fallback": "executor",
}


class DatabaseRunLogger:
    """Persist an execution log and the corresponding run status transition."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    async def log_node(
        self,
        run_id: object,
        node: str,
        status: str,
        message: str,
    ) -> None:
        """Write one node log and update lifecycle timestamps/status atomically."""
        if not isinstance(run_id, UUID):
            raise TypeError("run_id must be a UUID")
        now = datetime.now(UTC)
        async with self.session_factory() as session:
            run = await session.get(ResearchRun, run_id)
            if run is None:
                raise LookupError(f"Research run not found: {run_id}")
            run.status = status
            if run.started_at is None and status != "pending":
                run.started_at = now
            if status in {"completed", "failed", "cancelled"}:
                run.finished_at = now
                if run.started_at is not None:
                    run.total_duration_ms = max(
                        0, int((now - run.started_at).total_seconds() * 1000)
                    )
            session.add(
                ExecutionLog(
                    run_id=run_id,
                    node=_LOG_NODE_ALIASES.get(node, node),
                    level="INFO",
                    event="node_transition",
                    message=message,
                    data={"graph_node": node, "status": status},
                )
            )
            await session.commit()


async def set_run_error(
    session_factory: Any,
    run_id: UUID,
    *,
    status: str,
    error: str,
) -> None:
    """Persist terminal error or cancellation state and a system log."""
    now = datetime.now(UTC)
    async with session_factory() as session:
        run = await session.get(ResearchRun, run_id)
        if run is None:
            raise LookupError(f"Research run not found: {run_id}")
        run.status = status
        run.error = error
        run.finished_at = now
        if run.started_at is not None:
            run.total_duration_ms = max(0, int((now - run.started_at).total_seconds() * 1000))
        session.add(
            ExecutionLog(
                run_id=run_id,
                node="system",
                level="ERROR" if status == "failed" else "WARNING",
                event=f"run_{status}",
                message=error,
                data={"status": status},
            )
        )
        await session.commit()
