"""Run-bound structured logging with redaction and async persistence batching."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from structlog.contextvars import get_contextvars

from app.core.config import settings
from app.models.research import ExecutionLog, ResearchRun

_LOG_NODE_ALIASES = {
    "select_tool": "executor",
    "execute_tool": "executor",
    "collect": "executor",
    "retry_or_fallback": "executor",
}
_SECRET_KEY = re.compile(r"(key|token|password|secret)", re.IGNORECASE)
_TOKEN_COUNT_KEY = re.compile(r"(prompt|completion|total)_tokens?$", re.IGNORECASE)
_SECRET_VALUE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{12,}|bearer\s+[a-z0-9._~+/-]{12,}|"
    r"(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*\S+)"
)
REDACTED = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class _PendingLog:
    """One sanitized execution log waiting for its next flush boundary."""

    node: str
    level: str
    event: str
    message: str
    data: dict[str, Any]


class RunLogger:
    """Structured run logger writing immediately to stdout and batching DB writes."""

    def __init__(
        self,
        run_id: UUID,
        session_factory: Any,
        *,
        batch_size: int = 25,
        logger: Any | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.run_id = run_id
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.logger = logger or structlog.get_logger("researchpilot.run")
        self._pending: list[_PendingLog] = []
        self._status: str | None = None

    async def info(self, node: str, event: str, message: str, **data: Any) -> None:
        """Write an informational event."""
        await self._log("INFO", node, event, message, data)

    async def warn(self, node: str, event: str, message: str, **data: Any) -> None:
        """Write a warning event."""
        await self._log("WARNING", node, event, message, data)

    async def error(self, node: str, event: str, message: str, **data: Any) -> None:
        """Write an error event."""
        await self._log("ERROR", node, event, message, data)

    async def debug(self, node: str, event: str, message: str, **data: Any) -> None:
        """Write a debug event."""
        await self._log("DEBUG", node, event, message, data)

    async def llm_call(
        self,
        node: str,
        *,
        provider: str,
        model: str,
        prompt: str,
        latency_ms: int,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Record LLM metadata and a prompt hash, optionally logging prompt text."""
        details: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if settings.log_llm_prompts:
            details["prompt"] = prompt
        await self.info(node, "llm_call", "Language model request completed.", **details)

    async def log_node(
        self,
        run_id: object,
        node: str,
        status: str,
        message: str,
    ) -> None:
        """Record a graph-node status transition for compatibility with the runner."""
        if run_id != self.run_id:
            raise ValueError(f"Logger run id mismatch: {run_id}")
        self._status = status
        level = "ERROR" if status == "failed" else "INFO"
        await self._log(
            level,
            node,
            "node_transition",
            message,
            {"graph_node": node, "status": status},
        )

    async def set_status(self, status: str) -> None:
        """Set the lifecycle status to persist at the next flush."""
        self._status = status

    async def flush(self) -> None:
        """Persist the buffered logs and latest run status in one transaction."""
        if not self._pending and self._status is None:
            return
        pending = list(self._pending)
        status = self._status
        async with self.session_factory() as session:
            run = await session.get(ResearchRun, self.run_id)
            if run is None:
                raise LookupError(f"Research run not found: {self.run_id}")
            now = datetime.now(UTC)
            if status is not None:
                run.status = status
                if run.started_at is None and status != "pending":
                    run.started_at = now
                if status in {"completed", "failed", "cancelled"}:
                    run.finished_at = now
                    if run.started_at is not None:
                        run.total_duration_ms = max(
                            0, int((now - run.started_at).total_seconds() * 1000)
                        )
            session.add_all(
                [
                    ExecutionLog(
                        run_id=self.run_id,
                        node=_LOG_NODE_ALIASES.get(item.node, item.node),
                        level=item.level,
                        event=item.event,
                        message=item.message,
                        data=item.data,
                    )
                    for item in pending
                ]
            )
            await session.commit()
        del self._pending[: len(pending)]
        if self._status == status:
            self._status = None

    async def shutdown(self) -> None:
        """Flush any buffered logs when the run logger is closed."""
        await self.flush()

    async def _log(
        self,
        level: str,
        node: str,
        event: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        contextual_data = dict(data)
        request_id = get_contextvars().get("request_id")
        if isinstance(request_id, str):
            contextual_data.setdefault("request_id", request_id)
        safe_data = self.redact(contextual_data)
        item = _PendingLog(node, level, event, message, safe_data)
        self._pending.append(item)
        log_method_name = "warning" if level == "WARNING" else level.lower()
        log_method = getattr(self.logger, log_method_name)
        log_method(
            event,
            run_id=str(self.run_id),
            node=node,
            event_name=event,
            message=message,
            **safe_data,
        )
        if len(self._pending) >= self.batch_size:
            await self.flush()

    @classmethod
    def redact(cls, value: Any, *, key: str | None = None) -> Any:
        """Recursively redact sensitive fields and secret-like strings."""
        if key and _SECRET_KEY.search(key):
            if _TOKEN_COUNT_KEY.search(key) and isinstance(value, int | float):
                return value
            return REDACTED
        if isinstance(value, dict):
            return {
                str(child_key): cls.redact(child_value, key=str(child_key))
                for child_key, child_value in value.items()
            }
        if isinstance(value, list):
            return [cls.redact(item) for item in value]
        if isinstance(value, tuple):
            return [cls.redact(item) for item in value]
        if isinstance(value, str) and _SECRET_VALUE.search(value):
            return REDACTED
        return value
