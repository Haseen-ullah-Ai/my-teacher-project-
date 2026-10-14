"""Async engine and session dependency for SQLAlchemy."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection."""
    async with SessionLocal() as session:
        yield session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Backward-compatible alias for the existing API dependency."""
    async for session in get_session():
        yield session
