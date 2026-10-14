"""Add persisted run execution metrics.

Revision ID: 0002_run_metrics
Revises: 0001_initial_schema
"""

from __future__ import annotations

from alembic import op

revision = "0002_run_metrics"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add counters needed by run summaries and operational dashboards."""
    op.execute(
        """
        ALTER TABLE research_runs
            ADD COLUMN tool_call_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN failure_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN token_count BIGINT NOT NULL DEFAULT 0
        """
    )


def downgrade() -> None:
    """Remove persisted run metrics."""
    op.execute(
        """
        ALTER TABLE research_runs
            DROP COLUMN token_count,
            DROP COLUMN failure_count,
            DROP COLUMN retry_count,
            DROP COLUMN tool_call_count
        """
    )
