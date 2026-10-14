"""Unit tests for database schema/model serialization."""

from uuid import uuid4

from app.models.documents import DocumentChunk
from app.schemas.documents import DocumentChunkCreate, DocumentChunkRead


def test_document_chunk_metadata_maps_between_api_and_orm_names() -> None:
    """External `metadata` maps to a non-reserved ORM attribute and back."""
    document_id = uuid4()
    payload = DocumentChunkCreate(
        document_id=document_id,
        chunk_index=0,
        content="Indexed policy content",
        metadata={"page": 1},
    )
    row = DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        chunk_index=payload.chunk_index,
        content=payload.content,
        metadata_json=payload.metadata_json,
    )

    read_model = DocumentChunkRead.model_validate(row)

    assert read_model.metadata_json == {"page": 1}
    assert read_model.model_dump(by_alias=True)["metadata"] == {"page": 1}
