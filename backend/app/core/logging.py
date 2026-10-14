"""Structured logging setup used across the application."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from app.core.config import settings


def bind_context(**kwargs: str) -> None:
    """Bind request-specific structured context variables."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Reset context variables for future logging calls."""
    structlog.contextvars.clear_contextvars()


def configure_logging() -> None:
    """Configure JSON logs for the service."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


def get_logger(name: str) -> Any:
    """Return a structured logger bound to the current module name."""
    return structlog.get_logger(name)
