"""Create the initial ResearchPilot persistence schema.

Revision ID: 0001_initial_schema
Revises:
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the complete initial PostgreSQL schema."""
    op.execute(
        """
        CREATE TABLE research_runs (
            id UUID PRIMARY KEY,
            task TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            plan JSONB,
            final_report_id UUID,
            error TEXT,
            replan_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            total_duration_ms BIGINT,
            llm_provider VARCHAR(32) NOT NULL DEFAULT 'mock',
            CONSTRAINT ck_research_runs_status CHECK (
                status IN (
                    'pending', 'planning', 'running', 'analyzing', 'validating',
                    'reporting', 'completed', 'failed', 'cancelled'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE plan_steps (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            step_index INTEGER NOT NULL,
            description TEXT NOT NULL,
            tool_name VARCHAR(100) NOT NULL,
            tool_args JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            retries INTEGER NOT NULL DEFAULT 0,
            depends_on INTEGER[],
            CONSTRAINT ck_plan_steps_status CHECK (
                status IN ('pending', 'running', 'succeeded', 'failed', 'skipped')
            )
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_plan_steps_run_step ON plan_steps (run_id, step_index)")
    op.execute(
        """
        CREATE TABLE tool_calls (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            step_id UUID NOT NULL REFERENCES plan_steps(id) ON DELETE CASCADE,
            tool_name VARCHAR(100) NOT NULL,
            input JSONB NOT NULL DEFAULT '{}'::jsonb,
            output JSONB,
            status VARCHAR(20) NOT NULL,
            error_type VARCHAR(100),
            error_message TEXT,
            attempt INTEGER NOT NULL DEFAULT 1,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            duration_ms BIGINT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE execution_logs (
            id BIGSERIAL PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            step_id UUID REFERENCES plan_steps(id) ON DELETE SET NULL,
            node VARCHAR(20) NOT NULL,
            level VARCHAR(10) NOT NULL DEFAULT 'INFO',
            event VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_execution_logs_node CHECK (
                node IN (
                    'intake', 'planner', 'executor', 'analyzer', 'validator',
                    'reporter', 'system'
                )
            ),
            CONSTRAINT ck_execution_logs_level CHECK (
                level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_execution_logs_run_created_at ON execution_logs (run_id, created_at)"
    )
    op.execute(
        """
        CREATE TABLE findings (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            statement TEXT NOT NULL,
            evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence DOUBLE PRECISION NOT NULL,
            source_tool_call_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
            CONSTRAINT ck_findings_confidence CHECK (confidence >= 0 AND confidence <= 1)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE validation_results (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            attempt INTEGER NOT NULL,
            passed BOOLEAN NOT NULL,
            checks JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE reports (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            summary TEXT NOT NULL,
            content_json JSONB NOT NULL,
            content_markdown TEXT NOT NULL,
            file_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        ALTER TABLE research_runs
        ADD CONSTRAINT fk_research_runs_final_report_id
        FOREIGN KEY (final_report_id) REFERENCES reports(id)
        """
    )
    op.execute(
        """
        CREATE TABLE documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(500) NOT NULL,
            title VARCHAR(500) NOT NULL,
            checksum VARCHAR(128) NOT NULL UNIQUE,
            content_type VARCHAR(255) NOT NULL,
            size_bytes BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            tsv TSVECTOR GENERATED ALWAYS AS (
                to_tsvector('english'::regconfig, content)
            ) STORED NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT uq_document_chunks_document_index UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute("CREATE INDEX ix_document_chunks_tsv_gin ON document_chunks USING GIN (tsv)")
    op.execute(
        """
        CREATE TABLE datasets (
            id UUID PRIMARY KEY,
            filename VARCHAR(500) NOT NULL,
            checksum VARCHAR(128) NOT NULL UNIQUE,
            row_count BIGINT NOT NULL,
            columns JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    """Drop the schema in reverse dependency order."""
    op.execute("ALTER TABLE research_runs DROP CONSTRAINT fk_research_runs_final_report_id")
    op.execute("DROP TABLE datasets")
    op.execute("DROP TABLE document_chunks")
    op.execute("DROP TABLE documents")
    op.execute("DROP TABLE tool_calls")
    op.execute("DROP TABLE execution_logs")
    op.execute("DROP TABLE findings")
    op.execute("DROP TABLE validation_results")
    op.execute("DROP TABLE reports")
    op.execute("DROP TABLE plan_steps")
    op.execute("DROP TABLE research_runs")
