"""Repositories for document and dataset metadata."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Dataset, Document, DocumentChunk
from app.schemas.documents import DatasetCreate, DocumentChunkCreate, DocumentCreate


class DocumentRepository:
    """Data access for documents, chunks, and full-text search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: DocumentCreate) -> Document:
        """Create document metadata."""
        document = Document(**payload.model_dump())
        self.session.add(document)
        await self.session.flush()
        return document

    async def add_chunk(self, payload: DocumentChunkCreate) -> DocumentChunk:
        """Add a text chunk to a document."""
        chunk = DocumentChunk(**payload.model_dump())
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def get(self, document_id: UUID) -> Document | None:
        """Return a document by its identifier."""
        return await self.session.get(Document, document_id)

    async def get_by_checksum(self, checksum: str) -> Document | None:
        """Return a document by its content checksum."""
        result = await self.session.scalars(
            select(Document).where(Document.checksum == checksum).limit(1)
        )
        return result.first()

    async def search(self, query: str, limit: int = 20) -> Sequence[DocumentChunk]:
        """Search indexed document content with PostgreSQL full-text search."""
        rows = await self.search_with_titles(query=query, limit=limit)
        return [chunk for chunk, _title, _score in rows]

    async def search_with_titles(
        self,
        query: str,
        limit: int = 20,
        document_filter: str | None = None,
    ) -> Sequence[tuple[DocumentChunk, str, float]]:
        """Search chunks and return title and rank without async lazy-loading."""
        if not query.strip():
            return []
        tsquery = func.websearch_to_tsquery("english", query)
        statement = (
            select(DocumentChunk, Document.title, func.ts_rank_cd(DocumentChunk.tsv, tsquery))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.tsv.op("@@")(tsquery))
        )
        if document_filter is not None:
            statement = statement.where(Document.filename == document_filter)
        statement = (
            statement.order_by(func.ts_rank_cd(DocumentChunk.tsv, tsquery).desc())
            .limit(limit)
        )
        rows = await self.session.execute(statement)
        return [(chunk, title, float(score)) for chunk, title, score in rows.all()]


class DatasetRepository:
    """Data access for ingested dataset metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: DatasetCreate) -> Dataset:
        """Create dataset metadata."""
        dataset = Dataset(**payload.model_dump())
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def get(self, dataset_id: UUID) -> Dataset | None:
        """Return a dataset by its identifier."""
        return await self.session.get(Dataset, dataset_id)

    async def get_by_checksum(self, checksum: str) -> Dataset | None:
        """Return a dataset by its content checksum."""
        result = await self.session.scalars(
            select(Dataset).where(Dataset.checksum == checksum).limit(1)
        )
        return result.first()

    async def get_by_filename(self, filename: str) -> Dataset | None:
        """Return a registered dataset by its stored filename."""
        result = await self.session.scalars(
            select(Dataset).where(Dataset.filename == filename).limit(1)
        )
        return result.first()

    async def list_recent(self, limit: int = 50) -> Sequence[Dataset]:
        """Return newest datasets."""
        result = await self.session.scalars(
            select(Dataset).order_by(Dataset.created_at.desc()).limit(limit)
        )
        return result.all()
