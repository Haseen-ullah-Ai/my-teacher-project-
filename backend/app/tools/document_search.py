
"""PostgreSQL full-text document search tool."""

from __future__ import annotations

import re
from collections.abc import Callable
from html import unescape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ToolExecutionError
from app.repositories.documents import DocumentRepository
from app.tools.base import BaseTool
from app.tools.schemas import (
    DocumentSearchInput,
    DocumentSearchOutput,
    DocumentSearchResult,
)


class DocumentSearchTool(BaseTool[DocumentSearchInput, DocumentSearchOutput]):
    """Search registered document chunks with PostgreSQL full-text search."""

    name = "document_search"
    description = "Search ingested local policy and reference documents."
    input_model = DocumentSearchInput
    output_model = DocumentSearchOutput
    timeout = 20.0

    def __init__(
        self,
        session: AsyncSession | None = None,
        timeout: float | None = None,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        if timeout is not None:
            self.timeout = timeout

    async def run(self, input: DocumentSearchInput) -> DocumentSearchOutput:
        """Return ranked document chunks using a managed database session."""
        if self.session_factory is not None:
            async with self.session_factory() as session:
                rows = await DocumentRepository(session).search_with_titles(
                    query=input.query,
                    limit=input.top_k,
                    document_filter=input.document_filter,
                )
        elif self.session is not None:
            rows = await DocumentRepository(self.session).search_with_titles(
                query=input.query,
                limit=input.top_k,
                document_filter=input.document_filter,
            )
        else:
            raise ToolExecutionError(
                "Document search requires an async database session or session factory"
            )

        return DocumentSearchOutput(
            results=[
                DocumentSearchResult(
                    chunk_id=chunk.id,
                    document_title=title,
                    snippet=self._snippet(chunk.content, input.query),
                    rank_score=score,
                    chunk_index=chunk.chunk_index,
                )
                for chunk, title, score in rows
            ]
        )

    @staticmethod
    def _snippet(content: str, query: str, max_length: int = 500) -> str:
        """Return readable plain-text snippets without HTML markup."""
        text = unescape(content or "")

        # Remove embedded scripts and styles before removing HTML tags.
        text = re.sub(
            r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>",
            " ",
            text,
        )

        # Preserve readable separation between common HTML blocks.
        text = re.sub(
            r"(?i)<br\s*/?>|</(?:p|div|section|article|header|footer|li|h[1-6])\s*>",
            "\n",
            text,
        )

        # Remove remaining tags and decode HTML entities.
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = unescape(text)

        # Normalize excessive spaces and blank lines.
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        if len(text) <= max_length:
            return text

        terms = [
            term.strip("\"'()")
            for term in query.split()
            if term.strip("\"'()")
        ]

        lower_text = text.casefold()
        position = next(
            (
                found
                for term in terms
                if (found := lower_text.find(term.casefold())) >= 0
            ),
            0,
        )

        start = max(0, position - max_length // 3)
        end = min(len(text), start + max_length)
        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet += "..."

        return snippet


# """PostgreSQL full-text document search tool."""

# from __future__ import annotations

# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.errors import ToolExecutionError
# from app.repositories.documents import DocumentRepository
# from app.tools.base import BaseTool
# from app.tools.schemas import (
#     DocumentSearchInput,
#     DocumentSearchOutput,
#     DocumentSearchResult,
# )


# class DocumentSearchTool(BaseTool[DocumentSearchInput, DocumentSearchOutput]):
#     """Search registered document chunks with PostgreSQL full-text search."""

#     name = "document_search"
#     description = "Search ingested local policy and reference documents."
#     input_model = DocumentSearchInput
#     output_model = DocumentSearchOutput
#     timeout = 20.0

#     def __init__(self, session: AsyncSession | None = None, timeout: float | None = None) -> None:
#         self.session = session
#         if timeout is not None:
#             self.timeout = timeout

#     async def run(self, input: DocumentSearchInput) -> DocumentSearchOutput:
#         """Return ranked document chunks or a successful empty result list."""
#         if self.session is None:
#             raise ToolExecutionError("Document search requires an async database session")

#         rows = await DocumentRepository(self.session).search_with_titles(
#             query=input.query,
#             limit=input.top_k,
#             document_filter=input.document_filter,
#         )
#         return DocumentSearchOutput(
#             results=[
#                 DocumentSearchResult(
#                     chunk_id=chunk.id,
#                     document_title=title,
#                     snippet=self._snippet(chunk.content, input.query),
#                     rank_score=score,
#                     chunk_index=chunk.chunk_index,
#                 )
#                 for chunk, title, score in rows
#             ]
#         )

#     @staticmethod
#     def _snippet(content: str, query: str, max_length: int = 500) -> str:
#         """Return a bounded snippet centered around the first matching query term."""
#         if len(content) <= max_length:
#             return content
#         terms = [term.strip("\"'()") for term in query.split() if term.strip("\"'()")]
#         lower_content = content.lower()
#         position = next(
#             (
#                 lower_content.find(term.lower())
#                 for term in terms
#                 if lower_content.find(term.lower()) >= 0
#             ),
#             0,
#         )
#         start = max(0, position - max_length // 3)
#         end = min(len(content), start + max_length)
#         snippet = content[start:end].strip()
#         if start > 0:
#             snippet = "..." + snippet
#         if end < len(content):
#             snippet += "..."
#         return snippet
