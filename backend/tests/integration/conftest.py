"""Fixtures for isolated PostgreSQL integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session backed by a dedicated disposable PostgreSQL test database."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set TEST_DATABASE_URL to an isolated PostgreSQL database to run integration tests."
        )

    database_name = urlparse(database_url).path.rsplit("/", maxsplit=1)[-1]
    production_url = os.getenv("DATABASE_URL", "")
    if "test" not in database_name.lower() or database_url == production_url:
        pytest.fail("TEST_DATABASE_URL must point to a dedicated database with 'test' in its name.")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
