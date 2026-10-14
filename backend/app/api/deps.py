"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session to a route."""
    async for session in get_db_session():
        yield session


async def require_db(session: AsyncSession = Depends(get_db)) -> AsyncSession:
    """Validate that a database session exists."""
    return session
