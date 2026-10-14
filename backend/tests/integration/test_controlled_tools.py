"""PostgreSQL integration tests for database-backed controlled tools."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.documents import DatasetRepository, DocumentRepository
from app.schemas.documents import (
    DatasetColumn,
    DatasetCreate,
    DocumentChunkCreate,
    DocumentCreate,
)
from app.tools.csv_reader import CSVReaderTool
from app.tools.document_search import DocumentSearchTool

pytestmark = pytest.mark.asyncio


async def test_document_search_returns_ranked_database_chunks(db_session: AsyncSession) -> None:
    """PostgreSQL generated tsvector columns support relevant document search."""
    document = await DocumentRepository(db_session).create(
        DocumentCreate(
            filename="targets.md",
            title="Annual Sales Targets",
            checksum="integration-targets-checksum",
            content_type="text/markdown",
            size_bytes=70,
        )
    )
    chunk = await DocumentRepository(db_session).add_chunk(
        DocumentChunkCreate(
            document_id=document.id,
            chunk_index=0,
            content="North region quarterly revenue target is 250000 dollars.",
        )
    )

    result = await DocumentSearchTool(session=db_session).execute(
        {"query": "quarterly revenue target", "top_k": 5}
    )

    assert result.ok is True, result.error_message
    assert result.data["results"]
    assert result.data["results"][0]["chunk_id"] == str(chunk.id)
    assert result.data["results"][0]["document_title"] == "Annual Sales Targets"


async def test_document_repository_search_returns_chunks(db_session: AsyncSession) -> None:
    """Repository convenience search returns chunks rather than ranked tuples."""
    document = await DocumentRepository(db_session).create(
        DocumentCreate(
            filename="refunds.md",
            title="Refund Policy",
            checksum="integration-refund-checksum",
            content_type="text/markdown",
            size_bytes=50,
        )
    )
    chunk = await DocumentRepository(db_session).add_chunk(
        DocumentChunkCreate(
            document_id=document.id,
            chunk_index=0,
            content="Refunds are available within thirty days of purchase.",
        )
    )

    results = await DocumentRepository(db_session).search("refunds purchase")

    assert [item.id for item in results] == [chunk.id]


async def test_csv_reader_loads_registered_dataset(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    """CSV reads require matching registered metadata and use the actual DB repository."""
    csv_root = tmp_path / "csv"
    csv_root.mkdir()
    csv_path = csv_root / "targets.csv"
    content = b"region,target_revenue\nNorth,250000\nSouth,200000\n"
    csv_path.write_bytes(content)
    await DatasetRepository(db_session).create(
        DatasetCreate(
            filename="targets.csv",
            checksum=hashlib.sha256(content).hexdigest(),
            row_count=2,
            columns=[
                DatasetColumn(name="region", dtype="object"),
                DatasetColumn(name="target_revenue", dtype="int64"),
            ],
        )
    )

    result = await CSVReaderTool(session=db_session, data_root=tmp_path).execute(
        {"operation": "head", "filename": "targets.csv", "n": 2}
    )

    assert result.ok is True, result.error_message
    assert len(result.data["result"]) == 2
    assert result.data["provenance"]["dataset"] == "targets.csv"
