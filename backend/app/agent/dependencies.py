"""Dependencies shared by graph nodes during one agent run."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.base import LLMClient
from app.tools.registry import ToolRegistry


class RunLogger(Protocol):
    """Interface for persisted graph-node execution logging."""

    async def log_node(
        self,
        run_id: object,
        node: str,
        status: str,
        message: str,
    ) -> None:
        """Persist one node event and update the research-run status."""

SessionFactory = async_sessionmaker[AsyncSession] | Callable[[], AsyncSession]


@dataclass(slots=True)
class AgentDependencies:
    """Small dependency bundle passed explicitly to each graph node."""

    llm_client: LLMClient
    tool_registry: ToolRegistry
    session_factory: SessionFactory
    run_logger: RunLogger
