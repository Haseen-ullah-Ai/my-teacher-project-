"""Construct the configured provider-agnostic LLM client."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.errors import LLMError
from app.llm.base import LLMClient
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider


def get_llm_client(config: Any = settings) -> LLMClient:
    """Select the configured provider, defaulting to deterministic offline mock."""
    provider_name = str(config.llm_provider).lower()
    model = str(config.llm_model)
    api_key = config.llm_api_key
    if provider_name == "mock":
        return MockLLMProvider(model=model)
    if provider_name == "openai":
        return OpenAIProvider(model=model, api_key=api_key or "")
    if provider_name == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key or "")
    if provider_name == "ollama":
        return OllamaProvider(model=model)
    raise LLMError(f"Unsupported LLM provider: {provider_name}")


def build_llm_provider() -> LLMClient:
    """Backward-compatible alias for callers of the earlier provider factory."""
    return get_llm_client()
