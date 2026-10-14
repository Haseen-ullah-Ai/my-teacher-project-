"""Pydantic schemas for document and dataset records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """Create payload for an ingested document."""

    filename: str
    title: str
    checksum: str
    content_type: str
    size_bytes: int


class DocumentRead(DocumentCreate):
    """Read model for an ingested document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class DocumentChunkCreate(BaseModel):
    """Create payload for a document chunk."""

    document_id: UUID
    chunk_index: int
    content: str
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "metadata_json"),
        serialization_alias="metadata",
    )

    model_config = ConfigDict(populate_by_name=True)


class DocumentChunkRead(DocumentChunkCreate):
    """Read model for a document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    metadata_json: dict[str, Any] = Field(
        validation_alias="metadata_json",
        serialization_alias="metadata",
    )


class DatasetColumn(BaseModel):
    """Name and inferred dtype of one dataset column."""

    name: str
    dtype: str


class DatasetCreate(BaseModel):
    """Create payload for an ingested dataset."""

    filename: str
    checksum: str
    row_count: int
    columns: list[DatasetColumn]


class DatasetRead(DatasetCreate):
    """Read model for an ingested dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
