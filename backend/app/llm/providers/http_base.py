"""Common structured-output repair loop for HTTP-backed providers."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.errors import LLMError
from app.llm.base import LLMResponse, SchemaModel


class ProviderCompletion(BaseModel):
    """Unvalidated provider response and its token usage."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class HTTPStructuredLLMClient(ABC):
    """Shared one-repair-attempt behavior for remote JSON model providers."""

    def __init__(
        self,
        model: str,
        *,
        timeout_seconds: float = 60,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    async def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModel],
        system: str | None = None,
    ) -> LLMResponse[SchemaModel]:
        """Generate JSON and retry once when JSON/schema validation fails."""
        started = time.perf_counter()
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        contract = (
            "Return only a JSON object valid against this JSON Schema. "
            "Do not wrap the JSON in Markdown.\nJSON Schema:\n" + schema_text
        )
        request_prompt = prompt
        token_counts: list[tuple[int | None, int | None]] = []

        for attempt in range(2):
            try:
                completion = await self._complete(
                    request_prompt,
                    self._join_system(system, contract),
                    schema.model_json_schema(),
                )
            except Exception as exc:
                raise LLMError(f"{self.provider_name} request failed: {exc}") from exc
            token_counts.append((completion.prompt_tokens, completion.completion_tokens))

            try:
                output = schema.model_validate_json(completion.content)
            except (ValidationError, ValueError) as exc:
                if attempt == 0:
                    request_prompt = (
                        f"{prompt}\n\nThe previous response failed validation:\n{exc}\n"
                        "Correct the response and return only valid JSON."
                    )
                    continue
                raise LLMError(
                    f"{self.provider_name} returned invalid {schema.__name__} JSON after repair: "
                    f"{exc}"
                ) from exc

            prompt_tokens = self._sum_tokens(count[0] for count in token_counts)
            completion_tokens = self._sum_tokens(count[1] for count in token_counts)
            return LLMResponse[SchemaModel](
                output=output,
                model=completion.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=self._total_tokens(prompt_tokens, completion_tokens),
                latency_ms=self._elapsed_ms(started),
            )

        raise LLMError(f"{self.provider_name} failed to validate generated output")

    async def generate_text(
        self,
        prompt: str,
        system: str | None = None,
    ) -> LLMResponse[str]:
        """Generate text and return provider usage metadata."""
        started = time.perf_counter()
        try:
            completion = await self._complete(prompt, system, None)
        except Exception as exc:
            raise LLMError(f"{self.provider_name} request failed: {exc}") from exc
        return LLMResponse[str](
            output=completion.content,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            total_tokens=self._total_tokens(completion.prompt_tokens, completion.completion_tokens),
            latency_ms=self._elapsed_ms(started),
        )

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier for error messages."""

    @abstractmethod
    async def _complete(
        self,
        prompt: str,
        system: str | None,
        json_schema: dict[str, Any] | None,
    ) -> ProviderCompletion:
        """Send one provider request and extract its textual output."""

    async def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Post JSON and preserve provider error details for debugging."""
        if self.http_client is not None:
            response = await self.http_client.post(
                url, json=payload, headers=headers
            )
        else:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds
            ) as client:
                response = await client.post(
                    url, json=payload, headers=headers
                )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text

            raise LLMError(
                f"{self.provider_name} HTTP {response.status_code}: {detail}"
            ) from exc

        result = response.json()
        if not isinstance(result, dict):
            raise ValueError(
                "Provider returned a non-object JSON response"
            )
        return result
    @staticmethod
    def _join_system(system: str | None, contract: str) -> str:
        """Append the required JSON contract to provider system instructions."""
        return f"{system}\n\n{contract}" if system else contract

    @staticmethod
    def _usage_value(usage: dict[str, Any], *names: str) -> int | None:
        """Find an integer token count under provider-specific field names."""
        for name in names:
            value = usage.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _sum_tokens(values: Any) -> int | None:
        counts = [value for value in values if isinstance(value, int)]
        return sum(counts) if counts else None

    @staticmethod
    def _total_tokens(prompt_tokens: int | None, completion_tokens: int | None) -> int | None:
        if prompt_tokens is None and completion_tokens is None:
            return None
        return (prompt_tokens or 0) + (completion_tokens or 0)

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))
