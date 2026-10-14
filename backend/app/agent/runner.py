
"""Asynchronous run lifecycle, event streaming, and resumable graph execution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.dependencies import AgentDependencies, SessionFactory
from app.agent.graph import build_graph
from app.agent.persistence import DatabaseRunLogger, set_run_error
from app.agent.state import AgentState
from app.core.config import settings
from app.llm.factory import get_llm_client
from app.models.research import ExecutionLog, ResearchRun
from app.services.metrics import run_duration_seconds, runs_total
from app.services.run_logger import RunLogger
from app.tools.registry import build_default_registry


class AgentRunner:
    """Create research runs and execute them in cancellable background tasks."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        deps: AgentDependencies | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self.session_factory = session_factory
        self._custom_dependencies = deps is not None

        self.deps = deps or AgentDependencies(
            llm_client=get_llm_client(),
            tool_registry=build_default_registry(
                session_factory=session_factory
            ),
            session_factory=session_factory,
            run_logger=DatabaseRunLogger(session_factory),
        )

        self.checkpointer = (
            checkpointer if checkpointer is not None else MemorySaver()
        )
        self.graph = build_graph(
            self.deps,
            checkpointer=self.checkpointer,
        )

        self._tasks: dict[UUID, asyncio.Task[dict[str, Any]]] = {}
        self._event_queues: dict[
            UUID, asyncio.Queue[dict[str, Any] | None]
        ] = {}
        self._graphs: dict[UUID, Any] = {}
        self._run_started: dict[UUID, float] = {}
        self._run_loggers: dict[UUID, Any] = {}

    async def run(self, task: str) -> UUID:
        """Persist a pending run, start graph execution, and return its UUID."""
        run_id = uuid4()

        async with self.session_factory() as session:
            session.add(
                ResearchRun(
                    id=run_id,
                    task=task,
                    status="pending",
                    llm_provider=settings.llm_provider,
                    replan_count=0,
                )
            )
            await session.commit()

        if not self._custom_dependencies:
            run_logger = RunLogger(run_id, self.session_factory)
            run_dependencies = AgentDependencies(
                llm_client=self.deps.llm_client,
                tool_registry=build_default_registry(
                    session_factory=self.session_factory
                ),
                session_factory=self.session_factory,
                run_logger=run_logger,
            )
        else:
            run_dependencies = self.deps
            run_logger = self.deps.run_logger

        self._run_loggers[run_id] = run_logger
        self._graphs[run_id] = build_graph(
            run_dependencies,
            checkpointer=self.checkpointer,
        )
        self._run_started[run_id] = (
            asyncio.get_running_loop().time()
        )

        now = datetime.now(UTC)

        initial_state: AgentState = {
            "run_id": run_id,
            "task": task,
            "parsed_task": None,
            "plan": [],
            "current_step_index": 0,
            "tool_results": [],
            "findings": [],
            "analysis": None,
            "validation": None,
            "report": None,
            "errors": [],
            "retry_counts": {},
            "replan_count": 0,
            "status": "pending",
            "memory": [],
            "timestamps": {
                "created_at": now,
                "updated_at": now,
            },
            "last_tool_success": False,
            "last_error_type": None,
            "retry_requested": False,
            "skip_requested": False,
            "abort_requested": False,
            "pending_result": {},
            "active_evidence": [],
            "validation_feedback": [],
            "completed": False,
            "token_usage": {},
        }

        self._event_queues[run_id] = asyncio.Queue()
        self._tasks[run_id] = asyncio.create_task(
            self._execute(run_id, initial_state),
            name=f"research-run-{run_id}",
        )

        return run_id

    async def wait(self, run_id: UUID) -> dict[str, Any]:
        """Wait for a started run and return its final graph state."""
        try:
            task = self._tasks[run_id]
        except KeyError as exc:
            raise LookupError(
                f"No active or completed run found: {run_id}"
            ) from exc

        return await task

    async def cancel(self, run_id: UUID) -> None:
        """Cancel a running graph and persist its cancelled terminal state."""
        task = self._tasks.get(run_id)

        if task is None:
            raise LookupError(f"No active run found: {run_id}")

        if not task.done():
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

    async def resume(self, run_id: UUID) -> None:
        """Resume an interrupted graph from its in-memory run-id checkpoint."""
        config = {"configurable": {"thread_id": str(run_id)}}
        graph = self._graphs.get(run_id, self.graph)
        snapshot = await graph.aget_state(config)

        if not snapshot.values:
            raise LookupError(
                f"No checkpoint found for research run {run_id}"
            )

        if snapshot.values.get("status") == "completed":
            raise ValueError(
                f"Research run {run_id} is already terminal"
            )

        prior_task = self._tasks.get(run_id)

        if prior_task is not None and not prior_task.done():
            raise ValueError(
                f"Research run {run_id} is already active"
            )

        async with self.session_factory() as session:
            run = await session.get(ResearchRun, run_id)

            if run is None:
                raise LookupError(
                    f"Research run not found: {run_id}"
                )

            run.status = "pending"
            run.error = None
            run.finished_at = None

            session.add(
                ExecutionLog(
                    run_id=run_id,
                    node="system",
                    level="INFO",
                    event="run_resumed",
                    message=(
                        "Research run resumed from its in-memory checkpoint."
                    ),
                    data={"status": "pending"},
                )
            )
            await session.commit()

        logger = self._run_loggers.get(run_id)

        if logger is not None and hasattr(logger, "info"):
            run_dependencies = AgentDependencies(
                llm_client=self.deps.llm_client,
                tool_registry=build_default_registry(
                    session_factory=self.session_factory
                ),
                session_factory=self.session_factory,
                run_logger=logger,
            )

            self._graphs[run_id] = build_graph(
                run_dependencies,
                checkpointer=self.checkpointer,
            )

        self._event_queues[run_id] = asyncio.Queue()
        self._run_started[run_id] = (
            asyncio.get_running_loop().time()
        )
        self._tasks[run_id] = asyncio.create_task(
            self._execute(run_id, snapshot.values),
            name=f"research-run-resume-{run_id}",
        )

    async def stream_events(
        self,
        run_id: UUID,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield node-update events until execution ends."""
        try:
            queue = self._event_queues[run_id]
        except KeyError as exc:
            raise LookupError(
                f"No event stream exists for research run {run_id}"
            ) from exc

        while True:
            event = await queue.get()

            if event is None:
                break

            yield event

    async def _execute(
        self,
        run_id: UUID,
        initial_state: AgentState | None,
    ) -> dict[str, Any]:
        """Stream graph updates, persist terminal state, and report failures."""
        queue = self._event_queues[run_id]
        config = {"configurable": {"thread_id": str(run_id)}}
        graph = self._graphs.get(run_id, self.graph)
        run_logger = self._run_loggers.get(run_id)
        final_state: dict[str, Any] = {}

        try:
            async for update in graph.astream(
                initial_state,
                config=config,
                stream_mode="updates",
            ):
                for node, partial in update.items():
                    if isinstance(partial, dict):
                        final_state.update(partial)

                    await queue.put(
                        {
                            "run_id": str(run_id),
                            "node": node,
                            "update": self._json_safe(partial),
                        }
                    )

            await self._persist_run_metrics(
                run_id,
                final_state,
                "completed",
            )
            runs_total.labels(status="completed").inc()
            self._observe_run_duration(run_id)

            return final_state

        except asyncio.CancelledError:
            await set_run_error(
                self.session_factory,
                run_id,
                status="cancelled",
                error="Research run was cancelled.",
            )
            await self._persist_run_metrics(
                run_id,
                {},
                "cancelled",
            )

            if run_logger is not None and hasattr(run_logger, "warn"):
                await run_logger.warn(
                    "system",
                    "run_cancelled",
                    "Research run was cancelled.",
                )
                await run_logger.flush()

            runs_total.labels(status="cancelled").inc()
            self._observe_run_duration(run_id)

            await queue.put(
                {
                    "run_id": str(run_id),
                    "node": "system",
                    "status": "cancelled",
                }
            )
            raise

        except Exception as exc:
            await set_run_error(
                self.session_factory,
                run_id,
                status="failed",
                error=str(exc),
            )
            await self._persist_run_metrics(
                run_id,
                {"errors": [str(exc)]},
                "failed",
            )

            if run_logger is not None and hasattr(run_logger, "error"):
                await run_logger.error(
                    "system",
                    "run_failed",
                    "Research run failed.",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                await run_logger.flush()

            runs_total.labels(status="failed").inc()
            self._observe_run_duration(run_id)

            await queue.put(
                {
                    "run_id": str(run_id),
                    "node": "system",
                    "status": "failed",
                    "error": str(exc),
                }
            )
            raise

        finally:
            if run_logger is not None and hasattr(run_logger, "shutdown"):
                await run_logger.shutdown()

            await queue.put(None)

    async def _persist_run_metrics(
        self,
        run_id: UUID,
        state: dict[str, Any],
        status: str,
    ) -> None:
        """Persist terminal run counters and derive aggregates from graph state."""
        tool_results = state.get("tool_results", [])
        retry_counts = state.get("retry_counts", {})
        errors = state.get("errors", [])
        token_usage = state.get("token_usage", {})

        tool_call_count = int(
            state.get("tool_call_count", len(tool_results))
        )
        retry_count = int(
            state.get("retry_count", sum(retry_counts.values()))
        )

        failed_results = sum(
            1
            for result in tool_results
            if not (
                result.get("success", True)
                if isinstance(result, dict)
                else getattr(result, "success", True)
            )
        )

        failure_count = int(
            state.get("failure_count", failed_results + len(errors))
        )
        token_count = int(
            state.get("token_count", sum(token_usage.values()))
        )

        async with self.session_factory() as session:
            run = await session.get(ResearchRun, run_id)

            if run is None:
                raise LookupError(
                    f"Research run not found: {run_id}"
                )

            run.status = status
            run.tool_call_count = tool_call_count
            run.retry_count = retry_count
            run.failure_count = failure_count
            run.token_count = token_count
            run.replan_count = int(
                state.get("replan_count", run.replan_count)
            )

            elapsed = (
                asyncio.get_running_loop().time()
                - self._run_started.get(
                    run_id,
                    asyncio.get_running_loop().time(),
                )
            )

            run.total_duration_ms = max(
                0,
                int(elapsed * 1000),
            )

            await session.commit()

    def _observe_run_duration(self, run_id: UUID) -> None:
        """Observe elapsed wall-clock time for a terminal run."""
        elapsed = (
            asyncio.get_running_loop().time()
            - self._run_started.get(
                run_id,
                asyncio.get_running_loop().time(),
            )
        )

        run_duration_seconds.observe(max(0, elapsed))

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        """Convert node updates to JSON-compatible event payloads."""
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): cls._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                cls._json_safe(item)
                for item in value
            ]

        return value


def build_default_dependencies(
    session_factory: SessionFactory | None = None,
) -> AgentDependencies:
    """Construct dependencies for graph export and default runner instances."""
    from app.db.session import SessionLocal

    sessions: SessionFactory = (
        session_factory
        if session_factory is not None
        else SessionLocal
    )

    return AgentDependencies(
        llm_client=get_llm_client(),
        tool_registry=build_default_registry(
            session_factory=sessions
        ),
        session_factory=sessions,
        run_logger=DatabaseRunLogger(sessions),
    )





# """Asynchronous run lifecycle, event streaming, and resumable graph execution."""

# from __future__ import annotations

# import asyncio
# from collections.abc import AsyncIterator
# from datetime import UTC, datetime
# from typing import Any
# from uuid import UUID, uuid4

# from langgraph.checkpoint.memory import MemorySaver
# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# from app.agent.dependencies import AgentDependencies, SessionFactory
# from app.agent.graph import build_graph
# from app.agent.persistence import DatabaseRunLogger, set_run_error
# from app.agent.state import AgentState
# from app.core.config import settings
# from app.llm.factory import get_llm_client
# from app.models.research import ExecutionLog, ResearchRun
# from app.services.metrics import run_duration_seconds, runs_total
# from app.services.run_logger import RunLogger
# from app.tools.registry import build_default_registry


# class AgentRunner:
#     """Create research runs and execute them in cancellable background tasks."""

#     def __init__(
#         self,
#         session_factory: SessionFactory,
#         *,
#         deps: AgentDependencies | None = None,
#         checkpointer: Any | None = None,
#     ) -> None:
#         self.session_factory = session_factory
#         self._custom_dependencies = deps is not None
#         self.deps = deps or AgentDependencies(
#             llm_client=get_llm_client(),
#             tool_registry=build_default_registry(),
#             session_factory=session_factory,
#             run_logger=DatabaseRunLogger(session_factory),
#         )
#         self.checkpointer = checkpointer or MemorySaver()
#         self.graph = build_graph(self.deps, checkpointer=self.checkpointer)
#         self._tasks: dict[UUID, asyncio.Task[dict[str, Any]]] = {}
#         self._event_queues: dict[UUID, asyncio.Queue[dict[str, Any] | None]] = {}
#         self._graphs: dict[UUID, Any] = {}
#         self._run_started: dict[UUID, float] = {}
#         self._run_loggers: dict[UUID, Any] = {}

#     async def run(self, task: str) -> UUID:
#         """Persist a pending run, start graph execution, and return its UUID."""
#         run_id = uuid4()
#         async with self.session_factory() as session:
#             session.add(
#                 ResearchRun(
#                     id=run_id,
#                     task=task,
#                     status="pending",
#                     llm_provider=settings.llm_provider,
#                     replan_count=0,
#                 )
#             )
#             await session.commit()

#         run_logger: Any
#         if not self._custom_dependencies:
#             run_logger = RunLogger(run_id, self.session_factory)
#             run_dependencies = AgentDependencies(
#                 llm_client=self.deps.llm_client,
#                 tool_registry=self.deps.tool_registry,
#                 session_factory=self.session_factory,
#                 run_logger=run_logger,
#             )
#         else:
#             run_dependencies = self.deps
#             run_logger = self.deps.run_logger
#         self._run_loggers[run_id] = run_logger
#         self._graphs[run_id] = build_graph(
#             run_dependencies,
#             checkpointer=self.checkpointer,
#         )
#         self._run_started[run_id] = asyncio.get_running_loop().time()

#         now = datetime.now(UTC)
#         initial_state: AgentState = {
#             "run_id": run_id,
#             "task": task,
#             "parsed_task": None,
#             "plan": [],
#             "current_step_index": 0,
#             "tool_results": [],
#             "findings": [],
#             "analysis": None,
#             "validation": None,
#             "report": None,
#             "errors": [],
#             "retry_counts": {},
#             "replan_count": 0,
#             "status": "pending",
#             "memory": [],
#             "timestamps": {"created_at": now, "updated_at": now},
#             "last_tool_success": False,
#             "last_error_type": None,
#             "retry_requested": False,
#             "skip_requested": False,
#             "abort_requested": False,
#             "pending_result": {},
#             "active_evidence": [],
#             "validation_feedback": [],
#             "completed": False,
#             "token_usage": {},
#         }
#         self._event_queues[run_id] = asyncio.Queue()
#         self._tasks[run_id] = asyncio.create_task(
#             self._execute(run_id, initial_state),
#             name=f"research-run-{run_id}",
#         )
#         return run_id

#     async def wait(self, run_id: UUID) -> dict[str, Any]:
#         """Wait for a started run and return its final graph state."""
#         try:
#             task = self._tasks[run_id]
#         except KeyError as exc:
#             raise LookupError(f"No active or completed run found: {run_id}") from exc
#         return await task

#     async def cancel(self, run_id: UUID) -> None:
#         """Cancel a running graph and persist its cancelled terminal state."""
#         task = self._tasks.get(run_id)
#         if task is None:
#             raise LookupError(f"No active run found: {run_id}")
#         if not task.done():
#             task.cancel()
#             try:
#                 await task
#             except asyncio.CancelledError:
#                 pass

#     async def resume(self, run_id: UUID) -> None:
#         """Resume an interrupted graph from its in-memory run-id checkpoint."""
#         config = {"configurable": {"thread_id": str(run_id)}}
#         graph = self._graphs.get(run_id, self.graph)
#         snapshot = await graph.aget_state(config)
#         if not snapshot.values:
#             raise LookupError(f"No checkpoint found for research run {run_id}")
#         if snapshot.values.get("status") == "completed":
#             raise ValueError(f"Research run {run_id} is already terminal")
#         prior_task = self._tasks.get(run_id)
#         if prior_task is not None and not prior_task.done():
#             raise ValueError(f"Research run {run_id} is already active")
#         async with self.session_factory() as session:
#             run = await session.get(ResearchRun, run_id)
#             if run is None:
#                 raise LookupError(f"Research run not found: {run_id}")
#             run.status = "pending"
#             run.error = None
#             run.finished_at = None
#             session.add(
#                 ExecutionLog(
#                     run_id=run_id,
#                     node="system",
#                     level="INFO",
#                     event="run_resumed",
#                     message="Research run resumed from its in-memory checkpoint.",
#                     data={"status": "pending"},
#                 )
#             )
#             await session.commit()
#         logger = self._run_loggers.get(run_id)
#         if logger is not None and hasattr(logger, "info"):
#             run_dependencies = AgentDependencies(
#                 llm_client=self.deps.llm_client,
#                 tool_registry=self.deps.tool_registry,
#                 session_factory=self.session_factory,
#                 run_logger=logger,
#             )
#             self._graphs[run_id] = build_graph(
#                 run_dependencies,
#                 checkpointer=self.checkpointer,
#             )
#         self._event_queues[run_id] = asyncio.Queue()
#         self._run_started[run_id] = asyncio.get_running_loop().time()
#         self._tasks[run_id] = asyncio.create_task(
#             self._execute(run_id, snapshot.values),
#             name=f"research-run-resume-{run_id}",
#         )

#     async def stream_events(self, run_id: UUID) -> AsyncIterator[dict[str, Any]]:
#         """Yield node-update events from the per-run queue until execution ends."""
#         try:
#             queue = self._event_queues[run_id]
#         except KeyError as exc:
#             raise LookupError(f"No event stream exists for research run {run_id}") from exc
#         while True:
#             event = await queue.get()
#             if event is None:
#                 break
#             yield event

#     async def _execute(
#         self,
#         run_id: UUID,
#         initial_state: AgentState | None,
#     ) -> dict[str, Any]:
#         queue = self._event_queues[run_id]
#         config = {"configurable": {"thread_id": str(run_id)}}
#         graph = self._graphs.get(run_id, self.graph)
#         run_logger = self._run_loggers.get(run_id)
#         final_state: dict[str, Any] = {}
#         try:
#             async for update in graph.astream(
#                 initial_state,
#                 config=config,
#                 stream_mode="updates",
#             ):
#                 for node, partial in update.items():
#                     if isinstance(partial, dict):
#                         final_state.update(partial)
#                     await queue.put(
#                         {
#                             "run_id": str(run_id),
#                             "node": node,
#                             "update": self._json_safe(partial),
#                         }
#                     )
#             await self._persist_run_metrics(run_id, final_state, "completed")
#             runs_total.labels(status="completed").inc()
#             self._observe_run_duration(run_id)
#             return final_state
#         except asyncio.CancelledError:
#             await set_run_error(
#                 self.session_factory,
#                 run_id,
#                 status="cancelled",
#                 error="Research run was cancelled.",
#             )
#             await self._persist_run_metrics(run_id, {}, "cancelled")
#             if run_logger is not None and hasattr(run_logger, "warn"):
#                 await run_logger.warn(
#                     "system",
#                     "run_cancelled",
#                     "Research run was cancelled.",
#                 )
#                 await run_logger.flush()
#             runs_total.labels(status="cancelled").inc()
#             self._observe_run_duration(run_id)
#             await queue.put({"run_id": str(run_id), "node": "system", "status": "cancelled"})
#             raise
#         except Exception as exc:
#             await set_run_error(
#                 self.session_factory,
#                 run_id,
#                 status="failed",
#                 error=str(exc),
#             )
#             await self._persist_run_metrics(run_id, {"errors": [str(exc)]}, "failed")
#             if run_logger is not None and hasattr(run_logger, "error"):
#                 await run_logger.error(
#                     "system",
#                     "run_failed",
#                     "Research run failed.",
#                     error_type=type(exc).__name__,
#                     error=str(exc),
#                 )
#                 await run_logger.flush()
#             runs_total.labels(status="failed").inc()
#             self._observe_run_duration(run_id)
#             await queue.put(
#                 {
#                     "run_id": str(run_id),
#                     "node": "system",
#                     "status": "failed",
#                     "error": str(exc),
#                 }
#             )
#             raise
#         finally:
#             if run_logger is not None and hasattr(run_logger, "shutdown"):
#                 await run_logger.shutdown()
#             await queue.put(None)

#     async def _persist_run_metrics(
#         self,
#         run_id: UUID,
#         state: dict[str, Any],
#         status: str,
#     ) -> None:
#         """Persist terminal run counters and derive aggregates from graph state."""
#         tool_results = state.get("tool_results", [])
#         retry_counts = state.get("retry_counts", {})
#         errors = state.get("errors", [])
#         token_usage = state.get("token_usage", {})
#         tool_call_count = int(state.get("tool_call_count", len(tool_results)))
#         retry_count = int(state.get("retry_count", sum(retry_counts.values())))
#         failed_results = sum(
#             1
#             for result in tool_results
#             if not (
#                 result.get("success", True)
#                 if isinstance(result, dict)
#                 else getattr(result, "success", True)
#             )
#         )
#         failure_count = int(state.get("failure_count", failed_results + len(errors)))
#         token_count = int(state.get("token_count", sum(token_usage.values())))
#         async with self.session_factory() as session:
#             run = await session.get(ResearchRun, run_id)
#             if run is None:
#                 raise LookupError(f"Research run not found: {run_id}")
#             run.status = status
#             run.tool_call_count = tool_call_count
#             run.retry_count = retry_count
#             run.failure_count = failure_count
#             run.token_count = token_count
#             run.replan_count = int(state.get("replan_count", run.replan_count))
#             elapsed = asyncio.get_running_loop().time() - self._run_started.get(
#                 run_id, asyncio.get_running_loop().time()
#             )
#             run.total_duration_ms = max(0, int(elapsed * 1000))
#             await session.commit()

#     def _observe_run_duration(self, run_id: UUID) -> None:
#         """Observe elapsed wall-clock time once when a run reaches a terminal state."""
#         elapsed = asyncio.get_running_loop().time() - self._run_started.get(
#             run_id, asyncio.get_running_loop().time()
#         )
#         run_duration_seconds.observe(max(0, elapsed))

#     @classmethod
#     def _json_safe(cls, value: Any) -> Any:
#         """Convert node updates to JSON-compatible event payloads."""
#         if hasattr(value, "model_dump"):
#             return value.model_dump(mode="json")
#         if isinstance(value, UUID):
#             return str(value)
#         if isinstance(value, datetime):
#             return value.isoformat()
#         if isinstance(value, dict):
#             return {str(key): cls._json_safe(item) for key, item in value.items()}
#         if isinstance(value, list):
#             return [cls._json_safe(item) for item in value]
#         return value


# def build_default_dependencies(
#     session_factory: SessionFactory | None = None,
# ) -> AgentDependencies:
#     """Construct dependencies for graph export and default runner instances."""
#     from app.db.session import SessionLocal

#     sessions: SessionFactory | async_sessionmaker[AsyncSession] = (
#         session_factory if session_factory is not None else SessionLocal
#     )

#     return AgentDependencies(
#         llm_client=get_llm_client(),
#         tool_registry=build_default_registry(),
#         session_factory=sessions,
#         run_logger=DatabaseRunLogger(sessions),
#     )
