"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware.base import RequestResponseEndpoint

from app.agent.runner import AgentRunner
from app.api.routes import router
from app.api.v1_routes import datasets_router, documents_router, runs_router, stats_router
from app.core.config import settings
from app.core.logging import bind_context, clear_context, configure_logging
from app.db.session import SessionLocal
from app.services.metrics import render_metrics

APP_VERSION = "0.1.0"


async def database_status() -> str:
    """Return either 'ok' or 'down' depending on database connectivity."""
    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await engine.dispose()
        return "ok"
    except Exception:
        return "down"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks for the application."""
    configure_logging()
    yield


def create_app() -> FastAPI:
    """Build the FastAPI application factory."""
    app = FastAPI(title="ResearchPilot", version=APP_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(datasets_router, prefix="/api/v1", tags=["datasets"])
    app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
    app.include_router(runs_router, prefix="/api/v1", tags=["runs"])
    app.include_router(stats_router, prefix="/api/v1", tags=["stats"])
    app.state.agent_runner = AgentRunner(SessionLocal)

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Bind a stable request id to structured logs and echo it to clients."""
        request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid4())
        bind_context(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_context()

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return application and database health."""
        return {"status": "ok", "version": APP_VERSION, "db": await database_status()}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Expose Prometheus-compatible process and ResearchPilot metrics."""
        body, content_type = render_metrics()
        return Response(content=body, media_type=content_type)

    return app


app = create_app()
