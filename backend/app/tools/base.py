"""Validated asynchronous tool contracts and execution envelope."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import (
    ToolError,
    ToolExecutionError,
    ToolInputError,
    ToolTimeoutError,
)

InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)


class ToolResult(BaseModel):
    """Uniform result envelope returned by every tool invocation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ok: bool
    data: Any = None
    error_type: str | None = None
    error_message: str | None = None
    duration_ms: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC, Generic[InputModel, OutputModel]):
    """A controlled tool with validated input/output and timeout enforcement."""

    name: str
    description: str
    input_model: type[InputModel]
    output_model: type[OutputModel]
    timeout: float = 30.0

    @abstractmethod
    async def run(self, input: InputModel) -> OutputModel:
        """Execute the tool-specific operation."""

    async def execute(self, input: InputModel | dict[str, Any]) -> ToolResult:
        """Validate, timeout, execute, validate output, and normalize failures."""
        started_at = time.perf_counter()
        try:
            validated_input = self.input_model.model_validate(input)
        except ValidationError as exc:
            error = ToolInputError(f"Invalid input for {self.name}: {exc}")
            return self._failure(error, started_at)
        except Exception as exc:
            error = ToolInputError(f"Invalid input for {self.name}: {exc}")
            return self._failure(error, started_at)

        try:
            raw_output = await asyncio.wait_for(self.run(validated_input), timeout=self.timeout)
            validated_output = self.output_model.model_validate(raw_output)
            return ToolResult(
                ok=True,
                data=validated_output.model_dump(mode="json"),
                duration_ms=self._duration_ms(started_at),
                metadata={"tool_name": self.name},
            )
        except TimeoutError:
            return self._failure(
                ToolTimeoutError(f"Tool {self.name} exceeded {self.timeout:g} seconds"),
                started_at,
            )
        except ToolError as exc:
            return self._failure(exc, started_at)
        except ValidationError as exc:
            return self._failure(
                ToolExecutionError(f"Tool {self.name} returned invalid output: {exc}"),
                started_at,
            )
        except Exception as exc:
            return self._failure(
                ToolExecutionError(f"Tool {self.name} failed: {exc}"),
                started_at,
            )

    def _failure(self, error: ToolError, started_at: float) -> ToolResult:
        """Build a typed failure result with elapsed duration."""
        return ToolResult(
            ok=False,
            error_type=type(error).__name__,
            error_message=str(error),
            duration_ms=self._duration_ms(started_at),
            metadata={
                "tool_name": self.name,
                "transient": bool(getattr(error, "transient", False)),
            },
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        """Return elapsed wall-clock duration in integer milliseconds."""
        return max(0, int((time.perf_counter() - started_at) * 1000))


__all__ = ["BaseTool", "ToolResult"]
