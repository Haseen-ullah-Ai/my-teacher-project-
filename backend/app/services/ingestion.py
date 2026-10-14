"""Idempotent ingestion of controlled local documents and CSV datasets."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ValidationFailedError
from app.repositories.documents import DatasetRepository, DocumentRepository
from app.schemas.documents import (
    DatasetColumn,
    DatasetCreate,
    DocumentChunkCreate,
    DocumentCreate,
)

_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_DATASET_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Counts of newly ingested and checksum-skipped source files."""

    documents_added: int
    documents_skipped: int
    datasets_added: int
    datasets_skipped: int


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into bounded chunks near paragraph or sentence boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    normalized = text.strip()
    if not normalized:
        return []

    boundaries = [match.end() for match in _BOUNDARY_RE.finditer(normalized)]
    chunks: list[str] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        max_end = min(start + chunk_size, text_length)
        if text_length - start <= chunk_size:
            end = text_length
        else:
            sentence_boundaries = [
                boundary for boundary in boundaries if start < boundary <= max_end
            ]
            if sentence_boundaries:
                end = sentence_boundaries[-1]
            else:
                whitespace = normalized.rfind(" ", start, max_end + 1)
                end = whitespace if whitespace > start else max_end

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        if end - start <= overlap:
            start = end
            continue

        overlap_start = max(start + 1, end - overlap)
        next_boundaries = [boundary for boundary in boundaries if overlap_start <= boundary < end]
        if next_boundaries:
            start = next_boundaries[0]
        else:
            start = overlap_start
            while start < end and not normalized[start - 1].isspace():
                start += 1

    return chunks


def _read_csv_metadata(raw_content: bytes) -> tuple[int, list[DatasetColumn]]:
    """Read row count and infer compact column type metadata without loading all rows."""
    reader = csv.DictReader(io.StringIO(raw_content.decode("utf-8-sig"), newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV dataset must include a header row")

    observed_types: dict[str, set[str]] = {name: set() for name in reader.fieldnames}
    row_count = 0
    for row in reader:
        row_count += 1
        for name in reader.fieldnames:
            value = (row.get(name) or "").strip()
            if not value:
                continue
            if value.lstrip("+-").isdigit():
                observed_types[name].add("integer")
            else:
                try:
                    float(value)
                except ValueError:
                    observed_types[name].add("string")
                else:
                    observed_types[name].add("float")

    columns: list[DatasetColumn] = []
    for name in reader.fieldnames:
        types = observed_types[name]
        if not types:
            dtype = "unknown"
        elif "string" in types:
            dtype = "string"
        elif "float" in types:
            dtype = "float"
        else:
            dtype = "integer"
        columns.append(DatasetColumn(name=name, dtype=dtype))
    return row_count, columns


class IngestionService:
    """Register local documents and CSV datasets in PostgreSQL."""

    def __init__(self, session: AsyncSession, data_root: Path | None = None) -> None:
        self.session = session
        self.data_root = (data_root or settings.data_root).resolve()
        self.documents = DocumentRepository(session)
        self.datasets = DatasetRepository(session)

    async def ingest(self) -> IngestionResult:
        """Ingest all supported files under configured documents and CSV folders."""
        document_files = self._source_files("documents", {".md", ".txt"})
        dataset_files = self._source_files("csv", {".csv"})
        documents_added = documents_skipped = 0
        datasets_added = datasets_skipped = 0

        for path in document_files:
            self._validate_file_size(path, MAX_DOCUMENT_BYTES)
            raw_content = await asyncio.to_thread(path.read_bytes)
            checksum = hashlib.sha256(raw_content).hexdigest()
            if await self.documents.get_by_checksum(checksum) is not None:
                documents_skipped += 1
                continue

            content = raw_content.decode("utf-8")
            document = await self.documents.create(
                DocumentCreate(
                    filename=path.name,
                    title=self._document_title(path, content),
                    checksum=checksum,
                    content_type="text/markdown" if path.suffix.lower() == ".md" else "text/plain",
                    size_bytes=len(raw_content),
                )
            )
            for chunk_index, chunk in enumerate(chunk_text(content)):
                await self.documents.add_chunk(
                    DocumentChunkCreate(
                        document_id=document.id,
                        chunk_index=chunk_index,
                        content=chunk,
                        metadata_json={
                            "filename": path.name,
                            "chunk_index": chunk_index,
                        },
                    )
                )
            documents_added += 1

        for path in dataset_files:
            self._validate_file_size(path, MAX_DATASET_BYTES)
            raw_content = await asyncio.to_thread(path.read_bytes)
            checksum = hashlib.sha256(raw_content).hexdigest()
            if await self.datasets.get_by_checksum(checksum) is not None:
                datasets_skipped += 1
                continue

            row_count, columns = await asyncio.to_thread(_read_csv_metadata, raw_content)
            await self.datasets.create(
                DatasetCreate(
                    filename=path.name,
                    checksum=checksum,
                    row_count=row_count,
                    columns=columns,
                )
            )
            datasets_added += 1

        return IngestionResult(
            documents_added=documents_added,
            documents_skipped=documents_skipped,
            datasets_added=datasets_added,
            datasets_skipped=datasets_skipped,
        )

    @staticmethod
    def _validate_file_size(path: Path, maximum_bytes: int) -> None:
        """Reject oversized local inputs before reading the full file into memory."""
        file_size = path.stat().st_size
        if file_size > maximum_bytes:
            raise ValidationFailedError(
                f"Input file exceeds the {maximum_bytes}-byte limit: {path.name}"
            )

    def _source_files(self, directory: str, suffixes: set[str]) -> list[Path]:
        """Return sorted supported files while rejecting missing or escaped roots."""
        root = (self.data_root / directory).resolve()
        try:
            root.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError(f"Configured {directory} path escapes the data root") from exc
        if not root.is_dir():
            raise FileNotFoundError(f"Required ingestion directory does not exist: {root}")

        files: list[Path] = []
        for path in sorted(root.iterdir()):
            if path.suffix.lower() not in suffixes or not path.is_file():
                continue
            resolved = path.resolve()
            try:
                resolved.relative_to(self.data_root)
            except ValueError as exc:
                raise ValueError(f"Ingestion source escapes the data root: {path}") from exc
            files.append(resolved)
        return files

    @staticmethod
    def _document_title(path: Path, content: str) -> str:
        """Use the first Markdown heading or the filename stem as a title."""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return path.stem.replace("_", " ").title()
