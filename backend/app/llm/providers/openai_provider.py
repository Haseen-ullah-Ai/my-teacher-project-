"""OpenAI-compatible Chat Completions client using httpx."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.errors import LLMError
from app.llm.providers.http_base import HTTPStructuredLLMClient, ProviderCompletion


class OpenAIProvider(HTTPStructuredLLMClient):
    """OpenAI Chat Completions adapter with schema validation and repair."""

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(model, timeout_seconds=timeout_seconds, http_client=http_client)
        if not api_key:
            raise LLMError("LLM_API_KEY is required for the OpenAI provider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    async def _complete(
        self,
        prompt: str,
        system: str | None,
        json_schema: dict[str, Any] | None,
    ) -> ProviderCompletion:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        response = await self._post_json(
            f"{self.base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            choice = response["choices"][0]["message"]["content"]
            if not isinstance(choice, str):
                raise TypeError("message content was not text")
            usage = response.get("usage") or {}
            return ProviderCompletion(
                content=choice,
                model=str(response.get("model", self.model)),
                prompt_tokens=self._usage_value(usage, "prompt_tokens"),
                completion_tokens=self._usage_value(usage, "completion_tokens"),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Unexpected OpenAI response shape: {exc}") from exc
