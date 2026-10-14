"""Controlled random transient failures for chaos testing."""

from __future__ import annotations

import math
from random import Random

from app.core.errors import ToolExecutionError
from app.tools.base import BaseTool, InputModel, OutputModel


class FaultInjectingTool(BaseTool[InputModel, OutputModel]):
    """Wrap a tool and inject typed transient failures at a configured rate."""

    def __init__(
        self,
        wrapped: BaseTool[InputModel, OutputModel],
        failure_rate: float,
        *,
        random_source: Random | None = None,
    ) -> None:
        if not math.isfinite(failure_rate) or not 0 <= failure_rate <= 1:
            raise ValueError("failure_rate must be a finite value between 0 and 1")
        self.wrapped = wrapped
        self.failure_rate = failure_rate
        self.random_source = random_source or Random()
        self.name = wrapped.name
        self.description = wrapped.description
        self.input_model: type[InputModel] = wrapped.input_model
        self.output_model: type[OutputModel] = wrapped.output_model
        self.timeout = wrapped.timeout

    async def run(self, input: InputModel) -> OutputModel:
        """Inject an explicitly transient error or delegate to the wrapped tool."""
        if self.random_source.random() < self.failure_rate:
            raise ToolExecutionError(
                f"Chaos test injected a transient failure in {self.name}",
                transient=True,
            )
        return await self.wrapped.run(input)
