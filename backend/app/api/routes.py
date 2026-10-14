"""HTTP routes for the ResearchPilot API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_db
from app.schemas.research import ResearchReport, TaskRequest
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api")


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness endpoint."""
    return {"status": "ok"}


@router.post("/tasks", response_model=ResearchReport)
async def submit_task(
    payload: TaskRequest,
    session: AsyncSession = Depends(require_db),
) -> ResearchReport:
    """Submit a research task and return a structured report skeleton."""
    service = ResearchService(session=session)
    try:
        return await service.run_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
