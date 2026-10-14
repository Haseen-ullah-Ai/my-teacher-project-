"""Application-wide custom exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base exception for the application."""


class ToolError(AppError):
    """Base exception for local tool failures."""


class ToolTimeoutError(ToolError):
    """Raised when a tool exceeds its configured timeout."""


class ToolInputError(ToolError):
    """Raised when a tool receives invalid input."""


class ToolExecutionError(ToolError):
    """Raised when a local tool execution fails at runtime."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is unavailable."""


class PlanningError(AppError):
    """Raised when the agent cannot create a valid plan."""


class ValidationFailedError(AppError):
    """Raised when input validation fails."""


class LLMError(AppError):
    """Raised when the configured model provider fails."""
