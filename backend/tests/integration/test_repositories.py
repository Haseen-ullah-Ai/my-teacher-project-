"""PostgreSQL repository and full-text search integration tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import DocumentRepository, ResearchRunRepository
from app.schemas.documents import DocumentChunkCreate, DocumentCreate


@pytest.mark.asyncio
async def test_research_run_repository_round_trip(db_session: AsyncSession) -> None:
    """Runs can be created and retrieved through the repository."""
    repository = ResearchRunRepository(db_session)
    run = await repository.create("Analyze local quarterly sales")
    await db_session.commit()

    fetched = await repository.get(run.id)

    assert fetched is not None
    assert fetched.task == "Analyze local quarterly sales"
    assert fetched.status == "pending"


@pytest.mark.asyncio
async def test_document_full_text_search(db_session: AsyncSession) -> None:
    """The generated tsvector column finds matching document chunks."""
    documents = DocumentRepository(db_session)
    document = await documents.create(
        DocumentCreate(
            filename="policy.txt",
            title="Sales Policy",
            checksum="integration-policy-checksum",
            content_type="text/plain",
            size_bytes=53,
        )
    )
    await documents.add_chunk(
        DocumentChunkCreate(
            document_id=document.id,
            chunk_index=0,
            content="Regional sales targets must be reviewed every quarter.",
            metadata={"page": 1},
        )
    )
    await db_session.commit()

    matches = await documents.search("regional targets")

    assert len(matches) == 1
    assert "Regional sales targets" in matches[0].content
