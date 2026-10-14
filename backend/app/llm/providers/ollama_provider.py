"""Local Ollama chat API client using httpx."""

from __future__ import annotations

from typing import Any

import httpx

from app.llm.providers.http_base import HTTPStructuredLLMClient, ProviderCompletion


class OllamaProvider(HTTPStructuredLLMClient):
    """Ollama chat adapter with local structured-output validation and repair."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(model, timeout_seconds=timeout_seconds, http_client=http_client)
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "Ollama"

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
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if json_schema is not None:
            payload["format"] = json_schema
        response = await self._post_json(
            f"{self.base_url}/api/chat",
            payload,
            {"Content-Type": "application/json"},
        )
        try:
            content = response["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content was not text")
            prompt_tokens = response.get("prompt_eval_count")
            completion_tokens = response.get("eval_count")
            return ProviderCompletion(
                content=content,
                model=str(response.get("model", self.model)),
                prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
                completion_tokens=(
                    completion_tokens if isinstance(completion_tokens, int) else None
                ),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Unexpected Ollama response shape: {exc}") from exc
