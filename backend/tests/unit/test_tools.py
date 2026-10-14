"""Unit coverage for controlled tool contracts and local tools."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.errors import ToolNotFoundError
from app.tools.base import BaseTool
from app.tools.calculator import CalculatorTool
from app.tools.csv_reader import CSVReaderTool
from app.tools.document_search import DocumentSearchTool
from app.tools.registry import build_default_registry
from app.tools.report_generator import ReportGeneratorTool
from app.tools.schemas import (
    ReportDraft,
)


class _SlowInput(BaseModel):
    """Input for the execution timeout contract test."""

    value: int


class _SlowOutput(BaseModel):
    """Output for the execution timeout contract test."""

    value: int


class _SlowTool(BaseTool[_SlowInput, _SlowOutput]):
    """Small fake tool that exceeds its configured deadline."""

    name = "slow"
    description = "Test timeout behavior."
    input_model = _SlowInput
    output_model = _SlowOutput
    timeout = 0.01

    async def run(self, input: _SlowInput) -> _SlowOutput:
        await asyncio.sleep(0.1)
        return _SlowOutput(value=input.value)


class _OutputErrorTool(BaseTool[_SlowInput, _SlowOutput]):
    """Tool used to verify output schema validation."""

    name = "bad_output"
    description = "Test output validation."
    input_model = _SlowInput
    output_model = _SlowOutput

    async def run(self, input: _SlowInput) -> Any:
        return {"not_value": input.value}


@pytest.mark.asyncio
async def test_base_tool_validates_and_returns_typed_success() -> None:
    """Tool execution validates input and output and measures duration."""
    tool = CalculatorTool()

    result = await tool.execute({"expression": "2 + 3 * 4"})

    assert result.ok is True
    assert result.data["value"] == 14.0
    assert result.data["normalized_expression"] == "2 + 3 * 4"
    assert result.duration_ms >= 0
    assert result.metadata["tool_name"] == "calculator"


@pytest.mark.asyncio
async def test_base_tool_rejects_invalid_input() -> None:
    """Invalid payloads return a ToolInputError envelope."""
    result = await CalculatorTool().execute({"expression": ""})

    assert result.ok is False
    assert result.error_type == "ToolInputError"


@pytest.mark.asyncio
async def test_base_tool_enforces_timeout_and_output_schema() -> None:
    """Timeout and malformed tool output become typed failure envelopes."""
    timeout_result = await _SlowTool().execute({"value": 1})
    output_result = await _OutputErrorTool().execute({"value": 1})

    assert timeout_result.error_type == "ToolTimeoutError"
    assert output_result.error_type == "ToolExecutionError"


def test_calculator_supports_approved_functions() -> None:
    """The approved helper functions return expected numeric results."""
    tool = CalculatorTool()

    for expression, expected in (
        ("round(3.14159, 2)", 3.14),
        ("abs(-8)", 8.0),
        ("min(4, 2, 9)", 2.0),
        ("max(4, 2, 9)", 9.0),
        ("sum(4, 2, 9)", 15.0),
        ("sqrt(81)", 9.0),
        ("pct_change(100, 115)", 15.0),
        ("pct_of(25, 200)", 12.5),
        ("cagr(100, 121, 2)", 10.000000000000009),
    ):
        result = asyncio.run(tool.execute({"expression": expression}))
        assert result.ok is True, result.error_message
        assert result.data["value"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "().__class__",
        "9**9**9",
        "x + 1",
        "open('file')",
    ],
)
def test_calculator_rejects_injection_and_unapproved_syntax(expression: str) -> None:
    """Names, attributes, arbitrary calls, and excessive powers are rejected."""
    result = asyncio.run(CalculatorTool().execute({"expression": expression}))

    assert result.ok is False
    assert result.error_type in {"ToolInputError", "ToolExecutionError"}


@pytest.mark.asyncio
async def test_calculator_division_by_zero_is_typed() -> None:
    """Division by zero becomes an explicit execution error."""
    result = await CalculatorTool().execute({"expression": "10 / 0"})

    assert result.ok is False
    assert result.error_type == "ToolExecutionError"
    assert "zero" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_csv_reader_runs_operations_with_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registered CSV operations provide bounded results and source provenance."""
    from app.tools import csv_reader

    csv_root = tmp_path / "csv"
    csv_root.mkdir()
    file_path = csv_root / "sales.csv"
    content = b"region,revenue,units\nNorth,100.0,2\nSouth,200.0,3\nNorth,150.0,4\n"
    file_path.write_bytes(content)
    dataset = SimpleNamespace(
        filename="sales.csv",
        checksum=hashlib.sha256(content).hexdigest(),
    )

    class FakeDatasetRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_filename(self, filename: str) -> object | None:
            return dataset if filename == dataset.filename else None

    monkeypatch.setattr(csv_reader, "DatasetRepository", FakeDatasetRepository)
    tool = CSVReaderTool(session=object(), data_root=tmp_path)  # type: ignore[arg-type]
    operations = [
        ({"operation": "describe", "filename": "sales.csv"}, 3),
        ({"operation": "head", "filename": "sales.csv", "n": 2}, 2),
        (
            {
                "operation": "filter",
                "filename": "sales.csv",
                "column": "region",
                "operator": "eq",
                "value": "North",
            },
            2,
        ),
        (
            {
                "operation": "aggregate",
                "filename": "sales.csv",
                "group_by": ["region"],
                "metric_column": "revenue",
                "agg": "sum",
            },
            2,
        ),
        (
            {
                "operation": "top_n",
                "filename": "sales.csv",
                "column": "revenue",
                "n": 1,
            },
            1,
        ),
    ]

    for payload, expected_rows in operations:
        result = await tool.execute(payload)
        assert result.ok is True, result.error_message
        assert result.data["provenance"]["dataset"] == "sales.csv"
        assert result.data["provenance"]["row_count_scanned"] == 3
        assert len(result.data["result"]) == expected_rows


@pytest.mark.asyncio
async def test_csv_reader_rejects_path_traversal_before_database_lookup(
    tmp_path: Path,
) -> None:
    """Traversal filenames cannot escape the configured CSV data directory."""
    tool = CSVReaderTool(session=object(), data_root=tmp_path)  # type: ignore[arg-type]

    result = await tool.execute({"operation": "head", "filename": "../../etc/passwd"})

    assert result.ok is False
    assert result.error_type == "ToolInputError"


@pytest.mark.asyncio
async def test_csv_reader_reports_invalid_input_and_unknown_column(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema and column errors are returned as explicit tool input failures."""
    from app.tools import csv_reader

    csv_root = tmp_path / "csv"
    csv_root.mkdir()
    file_path = csv_root / "sales.csv"
    content = b"region,revenue\nNorth,100\n"
    file_path.write_bytes(content)

    class FakeDatasetRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_filename(self, _filename: str) -> object:
            return SimpleNamespace(
                filename="sales.csv", checksum=hashlib.sha256(content).hexdigest()
            )

    monkeypatch.setattr(csv_reader, "DatasetRepository", FakeDatasetRepository)
    tool = CSVReaderTool(session=object(), data_root=tmp_path)  # type: ignore[arg-type]

    invalid = await tool.execute({"operation": "filter", "filename": "sales.csv"})
    unknown_column = await tool.execute(
        {
            "operation": "top_n",
            "filename": "sales.csv",
            "column": "unknown",
        }
    )

    assert invalid.error_type == "ToolInputError"
    assert unknown_column.error_type == "ToolInputError"
    assert "unknown" in (unknown_column.error_message or "")


@pytest.mark.asyncio
async def test_document_search_empty_results_are_successful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty PostgreSQL search result is not an execution error."""
    from app.tools import document_search

    class FakeDocumentRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def search_with_titles(
            self,
            query: str,
            limit: int,
            document_filter: str | None,
        ) -> list[Any]:
            assert query == "nothing matches"
            assert limit == 5
            assert document_filter is None
            return []

    monkeypatch.setattr(document_search, "DocumentRepository", FakeDocumentRepository)
    result = await DocumentSearchTool(session=object()).execute({"query": "nothing matches"})

    assert result.ok is True
    assert result.data["results"] == []


@pytest.mark.asyncio
async def test_document_search_maps_ranked_chunk_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ranked repository hit is mapped into the public search result schema."""
    from app.tools import document_search

    chunk_id = uuid4()
    chunk = SimpleNamespace(
        id=chunk_id,
        content="Quarterly sales exceeded the regional revenue target.",
        chunk_index=4,
    )

    class FakeDocumentRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def search_with_titles(
            self,
            query: str,
            limit: int,
            document_filter: str | None,
        ) -> list[Any]:
            assert query == "revenue target"
            assert limit == 5
            assert document_filter == "targets.md"
            return [(chunk, "Annual Targets", 0.75)]

    monkeypatch.setattr(document_search, "DocumentRepository", FakeDocumentRepository)
    result = await DocumentSearchTool(session=object()).execute(
        {
            "query": "revenue target",
            "document_filter": "targets.md",
        }
    )

    assert result.ok is True
    assert result.data["results"][0] == {
        "chunk_id": str(chunk_id),
        "document_title": "Annual Targets",
        "snippet": chunk.content,
        "rank_score": 0.75,
        "chunk_index": 4,
    }


@pytest.mark.asyncio
async def test_document_repository_search_unpacks_ranked_tuples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository's convenience API extracts chunks from ranked tuple rows."""
    from app.repositories.documents import DocumentRepository

    chunk = SimpleNamespace(id=uuid4())

    async def fake_search_with_titles(
        self: DocumentRepository,
        query: str,
        limit: int = 20,
        document_filter: str | None = None,
    ) -> list[Any]:
        assert query == "regional target"
        assert limit == 20
        assert document_filter is None
        return [(chunk, "Annual Targets", 0.75)]

    monkeypatch.setattr(DocumentRepository, "search_with_titles", fake_search_with_titles)
    results = await DocumentRepository(session=object()).search("regional target")  # type: ignore[arg-type]

    assert results == [chunk]


@pytest.mark.asyncio
async def test_document_search_invalid_input_is_reported() -> None:
    """Search requires a non-empty query and bounded top-k."""
    result = await DocumentSearchTool(session=object()).execute({"query": "", "top_k": 1000})

    assert result.ok is False
    assert result.error_type == "ToolInputError"


@pytest.mark.asyncio
async def test_report_generator_writes_markdown_and_pdf(tmp_path: Path) -> None:
    """A valid report draft yields readable Markdown and a non-empty styled PDF."""
    draft = ReportDraft.model_validate(
        {
            "title": "Q3 Sales Report",
            "executive_summary": "North finished above the regional target.",
            "sections": [
                {
                    "heading": "Performance",
                    "body": "Gross sales were $220,000.",
                    "evidence_refs": [{"reference": "tool-call-1", "citation": "sales rows 1-20"}],
                }
            ],
            "findings": [
                {
                    "statement": "North exceeded its target.",
                    "evidence_refs": [{"reference": "tool-call-1", "citation": "sales rows 1-20"}],
                }
            ],
            "recommendations": ["Reconcile the outlier transaction."],
            "limitations": ["The source is a sample dataset."],
            "appendix_tables": [
                {
                    "title": "Regional totals",
                    "columns": ["Region", "Revenue"],
                    "rows": [["North", 220000]],
                }
            ],
        }
    )
    result = await ReportGeneratorTool(reports_dir=tmp_path).execute(draft.model_dump())

    assert result.ok is True, result.error_message
    markdown_path = Path(result.data["markdown_path"])
    pdf_path = Path(result.data["pdf_path"])
    assert markdown_path.is_file()
    assert pdf_path.is_file() and pdf_path.stat().st_size > 0
    assert "tool-call-1" in markdown_path.read_text(encoding="utf-8")


def test_report_generator_rejects_inconsistent_table_rows() -> None:
    """Malformed appendix rows fail schema validation."""
    result = asyncio.run(
        ReportGeneratorTool().execute(
            {
                "title": "Invalid",
                "executive_summary": "Summary",
                "sections": [],
                "appendix_tables": [{"title": "Table", "columns": ["A", "B"], "rows": [[1]]}],
            }
        )
    )

    assert result.ok is False
    assert result.error_type == "ToolInputError"


def test_registry_describes_tools_and_rejects_unknown_names() -> None:
    """The default registry exposes JSON schemas and typed missing-tool behavior."""
    registry = build_default_registry()

    assert {tool.name for tool in registry.list()} == {
        "document_search",
        "csv_reader",
        "calculator",
        "report_generator",
    }
    descriptions = registry.describe_all()
    assert descriptions[0]["input_schema"]["type"] == "object"
    with pytest.raises(ToolNotFoundError, match="not registered"):
        registry.get("shell")
