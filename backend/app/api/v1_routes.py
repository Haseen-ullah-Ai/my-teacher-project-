"""Versioned collection routes for research runs and local source files."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import AgentRunner
from app.api.deps import require_db
from app.core.config import settings
from app.models.documents import Document, DocumentChunk
from app.models.research import (
    ExecutionLog,
    Finding,
    PlanStep,
    Report,
    ResearchRun,
    ToolCall,
    ValidationResult,
)
from app.repositories.documents import DatasetRepository, DocumentRepository
from app.schemas.documents import (
    DatasetColumn,
    DatasetCreate,
    DocumentChunkCreate,
    DocumentCreate,
)
from app.services.ingestion import (
    MAX_DATASET_BYTES,
    MAX_DOCUMENT_BYTES,
    _read_csv_metadata,
    chunk_text,
)

datasets_router = APIRouter()
documents_router = APIRouter()
runs_router = APIRouter()
stats_router = APIRouter()


class RunCreateRequest(BaseModel):
    """Request body accepted when starting a research run."""

    task: str = Field(min_length=10, max_length=4000)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    max_replans: int | None = Field(default=None, ge=0, le=5)
    dataset_ids: list[UUID] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)


class RunItemResponse(BaseModel):
    """Frontend run-list representation of a persisted run."""

    run_id: UUID
    task: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    total_duration_ms: int | None
    tool_call_count: int
    retry_count: int
    failure_count: int
    token_count: int
    replan_count: int


class DatasetResponse(BaseModel):
    """Dataset metadata returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    checksum: str
    row_count: int
    columns: list[DatasetColumn]
    created_at: datetime


class DocumentResponse(BaseModel):
    """Document metadata returned to the frontend."""

    id: UUID
    filename: str
    title: str
    content_type: str
    size_bytes: int
    created_at: datetime
    chunk_count: int = 0


class DatasetPreviewResponse(DatasetResponse):
    """Dataset metadata and a bounded CSV row preview."""

    rows: list[dict[str, Any]]


class ToolCallResponse(BaseModel):
    """Frontend representation of one persisted tool attempt."""

    id: UUID
    tool_name: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    attempt: int
    duration_ms: int | None
    started_at: datetime
    step_id: UUID
    step_index: int | None


def _safe_upload_name(upload: UploadFile) -> str:
    """Return a plain filename and reject missing or unsafe upload names."""
    raw_name = (upload.filename or "").replace("\\", "/")
    filename = Path(raw_name).name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=422, detail="A valid filename is required.")
    return filename


async def _read_upload(upload: UploadFile, maximum_bytes: int) -> bytes:
    """Read a bounded upload and reject data that exceeds its endpoint limit."""
    content = await upload.read(maximum_bytes + 1)
    if len(content) > maximum_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file must not be empty.")
    return content


def _upload_target(folder: str, filename: str) -> Path:
    """Resolve an upload beneath its configured data subdirectory."""
    root = settings.data_root.resolve()
    directory = (root / folder).resolve()
    target = (directory / filename).resolve()
    if directory.parent != root or target.parent != directory:
        raise HTTPException(status_code=422, detail="Invalid upload path.")
    return target


async def _persist_upload(target: Path, content: bytes) -> None:
    """Write upload bytes without blocking the async request loop."""
    await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(target.write_bytes, content)


def _registered_data_file(folder: str, filename: str) -> Path:
    """Resolve a registered filename beneath its configured data folder."""
    root = settings.data_root.resolve()
    directory = (root / folder).resolve()
    target = (directory / filename).resolve()
    if directory.parent != root or target.parent != directory:
        raise HTTPException(status_code=404, detail="Registered source file is unavailable.")
    return target


async def _require_run(session: AsyncSession, run_id: UUID) -> ResearchRun:
    """Return a persisted run or raise the standard not-found response."""
    run = await session.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Research run {run_id} was not found.")
    return run


def _run_item(run: ResearchRun) -> RunItemResponse:
    """Map a persisted run into the frontend's compact run representation."""
    duration_ms = run.total_duration_ms
    if duration_ms is None and run.started_at is not None and run.finished_at is not None:
        duration_ms = max(0, int((run.finished_at - run.started_at).total_seconds() * 1000))
    return RunItemResponse(
        run_id=run.id,
        task=run.task,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=duration_ms,
        total_duration_ms=run.total_duration_ms,
        tool_call_count=run.tool_call_count,
        retry_count=run.retry_count,
        failure_count=run.failure_count,
        token_count=run.token_count,
        replan_count=run.replan_count,
    )


@datasets_router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    session: AsyncSession = Depends(require_db),
) -> list[DatasetResponse]:
    """List registered CSV datasets."""
    rows = await DatasetRepository(session).list_recent()
    return [DatasetResponse.model_validate(row) for row in rows]


@datasets_router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def preview_dataset(
    dataset_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(require_db),
) -> DatasetPreviewResponse:
    """Return registered dataset metadata and up to the requested CSV rows."""
    dataset = await DatasetRepository(session).get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} was not found.")
    target = _registered_data_file("csv", dataset.filename)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Registered dataset file is unavailable.")
    raw_content = await asyncio.to_thread(target.read_bytes)
    if hashlib.sha256(raw_content).hexdigest() != dataset.checksum:
        raise HTTPException(status_code=409, detail="Registered dataset file has changed.")
    try:
        reader = csv.DictReader(io.StringIO(raw_content.decode("utf-8-sig"), newline=""))
        rows = [dict(row) for _, row in zip(range(limit), reader)]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail="Registered dataset is not valid CSV.") from exc
    return DatasetPreviewResponse(
        **DatasetResponse.model_validate(dataset).model_dump(),
        rows=rows,
    )


@datasets_router.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(require_db),
) -> DatasetResponse:
    """Validate, persist, and register one local CSV dataset."""
    filename = _safe_upload_name(file)
    if Path(filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=415, detail="Dataset uploads must be CSV files.")
    content = await _read_upload(file, MAX_DATASET_BYTES)
    try:
        row_count, columns = _read_csv_metadata(content)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV dataset: {exc}") from exc

    checksum = hashlib.sha256(content).hexdigest()
    repository = DatasetRepository(session)
    existing = await repository.get_by_checksum(checksum)
    if existing is not None:
        return DatasetResponse.model_validate(existing)

    filename_match = await repository.get_by_filename(filename)
    if filename_match is not None:
        raise HTTPException(
            status_code=409,
            detail="A different dataset with this filename is already registered.",
        )
    target = _upload_target("csv", filename)
    if target.exists():
        raise HTTPException(status_code=409, detail="A file with this dataset filename exists.")
    await _persist_upload(target, content)
    try:
        dataset = await repository.create(
            DatasetCreate(
                filename=filename,
                checksum=checksum,
                row_count=row_count,
                columns=columns,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(target.unlink, missing_ok=True)
        raise
    return DatasetResponse.model_validate(dataset)


@documents_router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: AsyncSession = Depends(require_db),
) -> list[DocumentResponse]:
    """List registered documents and their chunk counts."""
    statement = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    result = await session.execute(statement)
    return [
        DocumentResponse.model_validate(
            {
                **{
                    key: getattr(document, key)
                    for key in (
                        "id",
                        "filename",
                        "title",
                        "content_type",
                        "size_bytes",
                        "created_at",
                    )
                },
                "chunk_count": chunk_count,
            }
        )
        for document, chunk_count in result.all()
    ]


@documents_router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(require_db),
) -> dict[str, Any]:
    """Return document metadata and its ordered persisted content chunks."""
    document = await DocumentRepository(session).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")
    result = await session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.all()
    return {
        **{
            key: getattr(document, key)
            for key in (
                "id",
                "filename",
                "title",
                "content_type",
                "size_bytes",
                "created_at",
            )
        },
        "chunk_count": len(chunks),
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    }


@documents_router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(require_db),
) -> DocumentResponse:
    """Validate, chunk, persist, and register one local text document."""
    filename = _safe_upload_name(file)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Document uploads must be TXT or Markdown.")
    content = await _read_upload(file, MAX_DOCUMENT_BYTES)
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Document must be UTF-8 text.") from exc

    checksum = hashlib.sha256(content).hexdigest()
    repository = DocumentRepository(session)
    existing = await repository.get_by_checksum(checksum)
    if existing is not None:
        return DocumentResponse(
            **{
                key: getattr(existing, key)
                for key in (
                    "id",
                    "filename",
                    "title",
                    "content_type",
                    "size_bytes",
                    "created_at",
                )
            },
            chunk_count=len(chunk_text(text_content)),
        )

    filename_match = await session.scalar(
        select(Document).where(Document.filename == filename).limit(1)
    )
    if filename_match is not None:
        raise HTTPException(
            status_code=409,
            detail="A different document with this filename is already registered.",
        )
    target = _upload_target("documents", filename)
    if target.exists():
        raise HTTPException(status_code=409, detail="A file with this document filename exists.")
    await _persist_upload(target, content)
    chunks = chunk_text(text_content)
    try:
        document = await repository.create(
            DocumentCreate(
                filename=filename,
                title=Path(filename).stem,
                checksum=checksum,
                content_type="text/markdown" if suffix == ".md" else "text/plain",
                size_bytes=len(content),
            )
        )
        for chunk_index, chunk in enumerate(chunks):
            await repository.add_chunk(
                DocumentChunkCreate(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=chunk,
                    metadata_json={"filename": filename, "chunk_index": chunk_index},
                )
            )
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(target.unlink, missing_ok=True)
        raise
    return DocumentResponse(
        **{
            key: getattr(document, key)
            for key in (
                "id",
                "filename",
                "title",
                "content_type",
                "size_bytes",
                "created_at",
            )
        },
        chunk_count=len(chunks),
    )


@runs_router.get("/runs")
async def list_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(require_db),
) -> dict[str, Any]:
    """Return a paginated list of persisted research runs."""
    statement = select(ResearchRun)
    count_statement = select(func.count(ResearchRun.id))
    if status_filter:
        statement = statement.where(ResearchRun.status == status_filter)
        count_statement = count_statement.where(ResearchRun.status == status_filter)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(ResearchRun.task.ilike(pattern))
        count_statement = count_statement.where(ResearchRun.task.ilike(pattern))
    total = int(await session.scalar(count_statement) or 0)
    rows = await session.scalars(
        statement.order_by(ResearchRun.created_at.desc()).offset(offset).limit(limit)
    )
    return {
        "items": [_run_item(run).model_dump(mode="json") for run in rows.all()],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@runs_router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(payload: RunCreateRequest, request: Request) -> dict[str, UUID]:
    """Persist and schedule a research task with the application runner."""
    runner: AgentRunner = request.app.state.agent_runner
    run_id = await runner.run(payload.task)
    return {"run_id": run_id}


@runs_router.get("/runs/{run_id}")
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(require_db),
) -> dict[str, Any]:
    """Return a run and its persisted plan, findings, validation, and report."""
    run = await _require_run(session, run_id)
    steps_result = await session.scalars(
        select(PlanStep).where(PlanStep.run_id == run_id).order_by(PlanStep.step_index)
    )
    findings_result = await session.scalars(
        select(Finding).where(Finding.run_id == run_id).order_by(Finding.id)
    )
    validation_result = await session.scalars(
        select(ValidationResult)
        .where(ValidationResult.run_id == run_id)
        .order_by(ValidationResult.attempt)
    )
    report_result = await session.scalars(
        select(Report).where(Report.run_id == run_id).order_by(Report.created_at.desc()).limit(1)
    )
    steps = steps_result.all()
    findings = findings_result.all()
    validations = validation_result.all()
    report = report_result.first()
    report_json = None
    if report is not None:
        report_json = {
            "id": report.id,
            "title": report.title,
            "summary": report.summary,
            "content_json": report.content_json,
            "content_markdown": report.content_markdown,
            "file_paths": report.file_paths,
            "created_at": report.created_at,
        }
    duration_ms = run.total_duration_ms
    if duration_ms is None and run.started_at is not None:
        end = run.finished_at or datetime.now(UTC)
        duration_ms = max(0, int((end - run.started_at).total_seconds() * 1000))
    return {
        "run_id": run.id,
        "task": run.task,
        "status": run.status,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": duration_ms,
        "total_duration_ms": run.total_duration_ms,
        "tool_call_count": run.tool_call_count,
        "retry_count": run.retry_count,
        "failure_count": run.failure_count,
        "token_count": run.token_count,
        "replan_count": run.replan_count,
        "plan": [
            {
                "id": str(step.id),
                "step_index": step.step_index,
                "description": step.description,
                "tool_name": step.tool_name,
                "tool_args": step.tool_args,
                "status": step.status,
                "retries": step.retries,
                "depends_on": step.depends_on,
            }
            for step in steps
        ]
        or run.plan
        or [],
        "findings": [
            {
                "id": str(finding.id),
                "statement": finding.statement,
                "confidence": finding.confidence,
                "evidence": finding.evidence,
            }
            for finding in findings
        ],
        "validation_results": [
            {
                "attempt": validation.attempt,
                "passed": validation.passed,
                "checks": validation.checks,
                "created_at": validation.created_at,
            }
            for validation in validations
        ],
        "summary": {
            "total_duration_ms": run.total_duration_ms,
            "tool_call_count": run.tool_call_count,
            "retry_count": run.retry_count,
            "failure_count": run.failure_count,
            "token_count": run.token_count,
            "replan_count": run.replan_count,
        },
        "final_report_id": run.final_report_id,
        "error": run.error,
        "report": report_json,
    }


@runs_router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: UUID,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(require_db),
) -> list[dict[str, Any]]:
    """Return persisted node and run events in database insertion order."""
    await _require_run(session, run_id)
    statement = (
        select(ExecutionLog)
        .where(ExecutionLog.run_id == run_id, ExecutionLog.id > after_id)
        .order_by(ExecutionLog.id)
        .limit(limit)
    )
    result = await session.scalars(statement)
    return [
        {
            "id": log.id,
            "run_id": log.run_id,
            "node": log.node,
            "type": log.event,
            "event": log.event,
            "level": log.level,
            "message": log.message,
            "data": log.data,
            "created_at": log.created_at,
        }
        for log in result.all()
    ]


@runs_router.get("/runs/{run_id}/logs")
async def get_run_logs(
    run_id: UUID,
    level: str | None = None,
    node: str | None = None,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(require_db),
) -> list[dict[str, Any]]:
    """Return persisted raw execution log records for one run."""
    await _require_run(session, run_id)
    statement = select(ExecutionLog).where(
        ExecutionLog.run_id == run_id,
        ExecutionLog.id > after_id,
    )
    if level is not None:
        normalized_level = level.upper()
        if normalized_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise HTTPException(status_code=422, detail="Unsupported execution log level.")
        statement = statement.where(ExecutionLog.level == normalized_level)
    if node is not None:
        statement = statement.where(ExecutionLog.node == node)
    result = await session.scalars(
        statement.order_by(ExecutionLog.id).limit(limit)
    )
    return [
        {
            "id": log.id,
            "run_id": log.run_id,
            "node": log.node,
            "level": log.level,
            "event": log.event,
            "message": log.message,
            "data": log.data,
            "created_at": log.created_at,
        }
        for log in result.all()
    ]


@runs_router.get("/runs/{run_id}/tool-calls", response_model=list[ToolCallResponse])
async def get_run_tool_calls(
    run_id: UUID,
    session: AsyncSession = Depends(require_db),
) -> list[ToolCallResponse]:
    """Return tool attempts and their recorded inputs, outputs, and duration."""
    await _require_run(session, run_id)
    result = await session.execute(
        select(ToolCall, PlanStep.step_index)
        .outerjoin(PlanStep, PlanStep.id == ToolCall.step_id)
        .where(ToolCall.run_id == run_id)
        .order_by(ToolCall.started_at, ToolCall.id)
    )
    return [
        ToolCallResponse(
            id=call.id,
            tool_name=call.tool_name,
            status=call.status,
            input=call.input,
            output=call.output,
            error_type=call.error_type,
            error_message=call.error_message,
            attempt=call.attempt,
            duration_ms=call.duration_ms,
            started_at=call.started_at,
            step_id=call.step_id,
            step_index=step_index,
        )
        for call, step_index in result.all()
    ]


@runs_router.get("/tools")
async def get_tools(request: Request) -> list[dict[str, Any]]:
    """Describe tools registered with this application's agent runner."""
    runner: AgentRunner = request.app.state.agent_runner
    return list(runner.deps.tool_registry.describe_all())


@stats_router.get("/stats/overview")
async def get_overview_stats(
    session: AsyncSession = Depends(require_db),
) -> dict[str, Any]:
    """Return dashboard aggregates for recent research activity."""
    now = datetime.now(UTC)
    day_start = datetime.combine(now.date() - timedelta(days=13), time.min, tzinfo=UTC)
    status_rows = await session.execute(
        select(ResearchRun.status, func.count(ResearchRun.id)).group_by(ResearchRun.status)
    )
    runs_by_status = {run_status: count for run_status, count in status_rows.all()}
    total_runs = sum(runs_by_status.values())
    successful_runs = runs_by_status.get("completed", 0) + runs_by_status.get(
        "completed_with_warnings", 0
    )
    average_duration = await session.scalar(
        select(func.avg(ResearchRun.total_duration_ms)).where(
            ResearchRun.total_duration_ms.is_not(None)
        )
    )
    total_tool_calls = int(await session.scalar(select(func.sum(ResearchRun.tool_call_count))) or 0)
    day_rows = await session.execute(
        select(func.date(ResearchRun.created_at), func.count(ResearchRun.id))
        .where(ResearchRun.created_at >= day_start)
        .group_by(func.date(ResearchRun.created_at))
    )
    counts_by_day = {day: count for day, count in day_rows.all()}
    runs_by_day = [
        {
            "date": (day_start.date() + timedelta(days=day_offset)).isoformat(),
            "count": int(counts_by_day.get(day_start.date() + timedelta(days=day_offset), 0)),
        }
        for day_offset in range(14)
    ]
    tool_rows = await session.execute(
        select(
            ToolCall.tool_name,
            func.count(ToolCall.id),
            func.sum(case((ToolCall.status == "failed", 1), else_=0)),
        ).group_by(ToolCall.tool_name)
    )
    tool_usage = [
        {"tool_name": tool_name, "count": count, "failures": failures or 0}
        for tool_name, count, failures in tool_rows.all()
    ]
    runs = await session.scalars(
        select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(10)
    )
    recent_runs = [_run_item(run).model_dump(mode="json") for run in runs.all()]
    failures_by_tool = [
        {"tool_name": item["tool_name"], "count": item["failures"]}
        for item in tool_usage
        if item["failures"]
    ]
    return {
        "total_runs": total_runs,
        "success_rate": successful_runs / total_runs if total_runs else 0.0,
        "average_duration_ms": float(average_duration or 0),
        "total_tool_calls": total_tool_calls,
        "runs_by_status": runs_by_status,
        "runs_by_day": runs_by_day,
        "tool_usage": tool_usage,
        "failures_by_tool": failures_by_tool,
        "recent_runs": recent_runs,
    }
