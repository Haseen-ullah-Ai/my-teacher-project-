"""Tests for document chunking and idempotent ingestion."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.ingestion import IngestionService, _read_csv_metadata, chunk_text


def test_chunk_text_empty_and_whitespace_input() -> None:
    """Empty input does not create empty database chunks."""
    assert chunk_text("") == []
    assert chunk_text(" \n \t ") == []


def test_chunk_text_respects_size_and_sentence_boundaries() -> None:
    """Chunks remain bounded and prefer sentence boundaries."""
    text = " ".join(f"Sentence number {index} has enough words." for index in range(80))

    chunks = chunk_text(text, chunk_size=240, overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 240 for chunk in chunks)
    assert all(chunk.endswith(".") for chunk in chunks[:-1])


def test_chunk_text_preserves_overlap() -> None:
    """Adjacent chunks retain overlapping source content."""
    sentence = "This is a useful policy sentence with searchable terms. "
    text = sentence * 90

    chunks = chunk_text(text, chunk_size=400, overlap=100)

    assert len(chunks) > 1
    assert any(chunks[index][-50:] in chunks[index + 1] for index in range(len(chunks) - 1))


def test_chunk_text_splits_paragraphs_without_exceeding_limit() -> None:
    """Paragraph separators are preferred when fitting the configured chunk size."""
    paragraphs = [
        f"Paragraph {index} describes a regional policy threshold." for index in range(12)
    ]

    chunks = chunk_text("\n\n".join(paragraphs), chunk_size=180, overlap=30)

    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)
    assert all(paragraph in "\n\n".join(chunks) for paragraph in paragraphs)


def test_csv_metadata_counts_rows_and_infers_column_types() -> None:
    """CSV metadata retains the header schema and counts rows with missing values."""
    row_count, columns = _read_csv_metadata(b"region,units,revenue\nNorth,4,12.50\nSouth,5,\n")

    assert row_count == 2
    assert [(column.name, column.dtype) for column in columns] == [
        ("region", "string"),
        ("units", "integer"),
        ("revenue", "float"),
    ]


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_by_checksum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second run skips existing document and CSV checksums."""
    from app.services import ingestion

    documents_dir = tmp_path / "documents"
    csv_dir = tmp_path / "csv"
    documents_dir.mkdir()
    csv_dir.mkdir()
    (documents_dir / "policy.md").write_text(
        "# Example Policy\n\nThe approved threshold is 94 percent.\n",
        encoding="utf-8",
    )
    (csv_dir / "targets.csv").write_text(
        "region,target\nNorth,100\n",
        encoding="utf-8",
    )

    state: dict[str, set[str]] = {"documents": set(), "datasets": set()}

    class FakeDocumentRepository:
        def __init__(self, _session: object) -> None:
            self.state = state["documents"]

        async def get_by_checksum(self, checksum: str) -> object | None:
            return SimpleNamespace(id=uuid4()) if checksum in self.state else None

        async def create(self, payload: object) -> SimpleNamespace:
            self.state.add(payload.checksum)
            return SimpleNamespace(id=uuid4())

        async def add_chunk(self, _payload: object) -> None:
            return None

    class FakeDatasetRepository:
        def __init__(self, _session: object) -> None:
            self.state = state["datasets"]

        async def get_by_checksum(self, checksum: str) -> object | None:
            return SimpleNamespace(id=uuid4()) if checksum in self.state else None

        async def create(self, payload: object) -> SimpleNamespace:
            self.state.add(payload.checksum)
            return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(ingestion, "DocumentRepository", FakeDocumentRepository)
    monkeypatch.setattr(ingestion, "DatasetRepository", FakeDatasetRepository)
    service = IngestionService(session=object(), data_root=tmp_path)  # type: ignore[arg-type]

    first = await service.ingest()
    second = await service.ingest()

    assert first.documents_added == 1
    assert first.datasets_added == 1
    assert second.documents_added == 0
    assert second.documents_skipped == 1
    assert second.datasets_added == 0
    assert second.datasets_skipped == 1
