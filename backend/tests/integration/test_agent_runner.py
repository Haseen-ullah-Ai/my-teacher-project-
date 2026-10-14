"""PostgreSQL integration coverage for agent-run lifecycle persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.runner import AgentRunner
from app.models.research import ExecutionLog, ResearchRun


async def test_stub_agent_run_persists_completion_and_all_node_logs(
    db_session: AsyncSession,
) -> None:
    """A full stub graph persists its final status and graph-node events."""
    assert db_session.bind is not None
    session_factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    runner = AgentRunner(session_factory)

    run_id = await runner.run("Analyze Q3 sales")
    state = await runner.wait(run_id)

    async with session_factory() as session:
        run = await session.get(ResearchRun, run_id)
        logs = (
            await session.scalars(
                select(ExecutionLog).where(ExecutionLog.run_id == run_id).order_by(ExecutionLog.id)
            )
        ).all()

    assert state["status"] == "completed"
    assert run is not None and run.status == "completed"
    assert run.started_at is not None and run.finished_at is not None
    assert {log.node for log in logs} >= {
        "intake",
        "planner",
        "executor",
        "analyzer",
        "validator",
        "reporter",
    }
