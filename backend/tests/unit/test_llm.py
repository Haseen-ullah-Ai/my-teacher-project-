"""Offline tests for the structured LLM abstraction and provider factory."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.errors import LLMError
from app.llm.base import LLMResponse
from app.llm.factory import get_llm_client
from app.llm.prompts import render_prompt
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.schemas import AnalysisResult, ReporterOutput, ResearchPlan


@pytest.mark.asyncio
async def test_mock_planner_is_deterministic_and_validates_plan() -> None:
    """Keyword rules always return a Pydantic-valid multi-step research plan."""
    client = MockLLMProvider()
    prompt = "Analyze sales revenue, compare policy targets, and compute percent growth."

    first = await client.generate_structured(prompt, ResearchPlan)
    second = await client.generate_structured(prompt, ResearchPlan)

    assert first.output == second.output
    assert [step.tool_name for step in first.output.steps] == [
        "csv_reader",
        "document_search",
        "calculator",
    ]
    assert first.output.steps[0].tool_args["filename"] == "sales_2025.csv"
    assert first.output.steps[2].depends_on == [0, 1]
    assert first.model == "mock-model"


@pytest.mark.asyncio
async def test_mock_analyzer_cites_successful_tool_results_only() -> None:
    """Analyzer findings only use ids and outcomes present in supplied tool data."""
    client = MockLLMProvider()
    tool_results = [
        {
            "tool_name": "csv_reader",
            "tool_call_id": "db4d68e2-77cd-4be0-aaf3-49cb3c89d3a9",
            "success": True,
            "data": {"result": [{"region": "North"}, {"region": "South"}]},
        },
        {
            "tool_name": "document_search",
            "tool_call_id": "failed-call",
            "success": False,
            "data": {},
        },
    ]
    prompt = render_prompt(
        "analyzer",
        task="Summarize the collected rows",
        tool_results=tool_results,
    )

    response = await client.generate_structured(prompt, AnalysisResult)

    assert len(response.output.findings) == 1
    finding = response.output.findings[0]
    assert finding.statement == "The csv_reader tool returned 2 result row(s)."
    assert finding.evidence_refs[0].reference == tool_results[0]["tool_call_id"]
    assert str(finding.source_tool_call_ids[0]) == tool_results[0]["tool_call_id"]
    assert "failed-call" not in finding.evidence_refs[0].reference


@pytest.mark.asyncio
async def test_mock_reporter_validates_and_preserves_analysis_citations() -> None:
    """Reporter output validates and reuses evidence references from analysis."""
    client = MockLLMProvider()
    analysis = {
        "summary": "One cited observation.",
        "findings": [
            {
                "statement": "The source returned one row.",
                "evidence_refs": [{"reference": "call-1", "citation": "CSV result from call-1"}],
            }
        ],
        "recommendations": ["Review the source result."],
        "limitations": [],
    }
    prompt = render_prompt(
        "reporter",
        task="Summarize the dataset",
        analysis=analysis,
        tool_results=[],
    )

    response = await client.generate_structured(prompt, ReporterOutput)

    assert response.output.executive_summary == "One cited observation."
    assert response.output.findings[0].evidence_refs[0].reference == "call-1"
    assert response.output.sections[0].evidence_refs[0].reference == "call-1"


@pytest.mark.asyncio
async def test_mock_text_response_has_usage_and_latency_metadata() -> None:
    """Text output uses the common response wrapper without contacting a provider."""
    response = await MockLLMProvider().generate_text("test prompt")

    assert isinstance(response, LLMResponse)
    assert "No external model or network was used" in response.output
    assert response.latency_ms >= 0
    assert response.total_tokens is None


@pytest.mark.asyncio
async def test_openai_provider_repairs_invalid_structured_response_once() -> None:
    """A schema-invalid first response is included in one deterministic repair request."""
    request_payloads: list[dict[str, object]] = []
    answer = {
        "steps": [
            {
                "description": "Search the policy",
                "tool_name": "document_search",
                "tool_args": {"query": "policy"},
                "depends_on": [],
            }
        ]
    }

    async def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        request_payloads.append(body)
        content = "not-json" if len(request_payloads) == 1 else json.dumps(answer)
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        client = OpenAIProvider(
            "test-model",
            "test-key",
            base_url="https://test.invalid/v1",
            http_client=http_client,
        )
        response = await client.generate_structured("Plan this task", ResearchPlan)

    assert response.output == ResearchPlan.model_validate(answer)
    assert len(request_payloads) == 2
    repair_prompt = request_payloads[1]["messages"][-1]["content"]  # type: ignore[index]
    assert "previous response failed validation" in repair_prompt.lower()
    assert response.prompt_tokens == 8
    assert response.completion_tokens == 6
    assert response.total_tokens == 14


@pytest.mark.asyncio
async def test_provider_wraps_transport_failures_as_llm_error() -> None:
    """Provider request exceptions never leak as unrelated exception types."""

    def fail_request(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="provider unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail_request)) as http_client:
        client = OpenAIProvider(
            "test-model",
            "test-key",
            base_url="https://test.invalid/v1",
            http_client=http_client,
        )

        with pytest.raises(LLMError, match="OpenAI request failed"):
            await client.generate_text("hello")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["anthropic", "ollama"])
async def test_http_providers_request_json_and_parse_usage(provider_name: str) -> None:
    """Anthropic and Ollama adapters send structured requests through httpx."""
    received: list[httpx.Request] = []
    output = {
        "steps": [
            {
                "description": "Search local documents",
                "tool_name": "document_search",
                "tool_args": {"query": "sales policy"},
                "depends_on": [],
            }
        ]
    }

    async def respond(request: httpx.Request) -> httpx.Response:
        received.append(request)
        if provider_name == "anthropic":
            body = {
                "model": "anthropic-test",
                "content": [{"type": "text", "text": json.dumps(output)}],
                "usage": {"input_tokens": 5, "output_tokens": 4},
            }
        else:
            body = {
                "model": "ollama-test",
                "message": {"content": json.dumps(output)},
                "prompt_eval_count": 5,
                "eval_count": 4,
            }
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        if provider_name == "anthropic":
            client = AnthropicProvider("test-model", "test-key", http_client=http_client)
        else:
            client = OllamaProvider("test-model", http_client=http_client)
        response = await client.generate_structured("Create a plan", ResearchPlan)

    assert response.output == ResearchPlan.model_validate(output)
    assert response.prompt_tokens == 5
    assert response.completion_tokens == 4
    request_body = json.loads(received[0].content)
    if provider_name == "anthropic":
        assert received[0].url.path.endswith("/messages")
        assert "JSON Schema" in request_body["system"]
    else:
        assert received[0].url.path.endswith("/api/chat")
        assert request_body["format"]["type"] == "object"


def test_factory_selects_configured_provider_without_requests() -> None:
    """Factory selection constructs all providers and rejects absent required keys."""

    def config(provider: str, key: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            llm_provider=provider,
            llm_model="test-model",
            llm_api_key=key,
        )

    assert isinstance(get_llm_client(config("mock")), MockLLMProvider)
    assert isinstance(get_llm_client(config("openai", "key")), OpenAIProvider)
    assert isinstance(get_llm_client(config("anthropic", "key")), AnthropicProvider)
    assert isinstance(get_llm_client(config("ollama")), OllamaProvider)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        get_llm_client(config("openai"))
    with pytest.raises(LLMError, match="Unsupported"):
        get_llm_client(config("unknown"))


def test_prompt_templates_are_loaded_from_versioned_local_files() -> None:
    """All workflow prompt templates render with explicit JSON contracts."""
    planner = render_prompt("planner")
    analyzer = render_prompt("analyzer", task="task", tool_results=[])
    validator = render_prompt("validator", task="task", report={}, tool_results=[])
    reporter = render_prompt("reporter", task="task", analysis={}, tool_results=[])

    for prompt in (planner, analyzer, validator, reporter):
        assert "Version: 1.0.0" in prompt
        assert "Output contract" in prompt
    assert "ResearchPlan" in planner
    assert "never invent" in analyzer.lower()
    with pytest.raises(ValueError, match="Unknown prompt"):
        render_prompt("unknown")
