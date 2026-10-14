"""Shared provider-agnostic language model contracts."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

OutputModel = TypeVar("OutputModel")
SchemaModel = TypeVar("SchemaModel", bound=BaseModel)


class LLMResponse(BaseModel, Generic[OutputModel]):
    """Model output with provider usage and elapsed-time metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: OutputModel
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int


class LLMClient(Protocol):
    """Common asynchronous interface implemented by every provider."""

    async def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModel],
        system: str | None = None,
    ) -> LLMResponse[SchemaModel]:
        """Generate and validate structured output matching a Pydantic schema."""
        ...

    async def generate_text(
        self,
        prompt: str,
        system: str | None = None,
    ) -> LLMResponse[str]:
        """Generate a text response."""
        ...
