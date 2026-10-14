"""Anthropic Messages API client using httpx."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.errors import LLMError
from app.llm.providers.http_base import HTTPStructuredLLMClient, ProviderCompletion


class AnthropicProvider(HTTPStructuredLLMClient):
    """Anthropic Messages adapter with schema validation and repair."""

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        base_url: str = "https://api.anthropic.com/v1",
        timeout_seconds: float = 60,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(model, timeout_seconds=timeout_seconds, http_client=http_client)
        if not api_key:
            raise LLMError("LLM_API_KEY is required for the Anthropic provider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    async def _complete(
        self,
        prompt: str,
        system: str | None,
        json_schema: dict[str, Any] | None,
    ) -> ProviderCompletion:
        system_text = system or ""
        if json_schema is not None:
            system_text += "\nReturn only JSON conforming to this JSON Schema:\n" + json.dumps(
                json_schema, ensure_ascii=False
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_text:
            payload["system"] = system_text
        response = await self._post_json(
            f"{self.base_url}/messages",
            payload,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            content = "".join(
                block["text"]
                for block in response["content"]
                if block.get("type") == "text" and isinstance(block.get("text"), str)
            )
            usage = response.get("usage") or {}
            return ProviderCompletion(
                content=content,
                model=str(response.get("model", self.model)),
                prompt_tokens=self._usage_value(usage, "input_tokens"),
                completion_tokens=self._usage_value(usage, "output_tokens"),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Unexpected Anthropic response shape: {exc}") from exc
