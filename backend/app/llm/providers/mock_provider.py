"""Deterministic, rule-based LLM provider for demos and offline testing only."""

from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import UUID

from app.core.errors import LLMError
from app.llm.base import LLMResponse, SchemaModel
from app.llm.schemas import AnalysisResult, ReporterOutput, ResearchPlan


class MockLLMProvider:
    """No-network demo provider; outputs are deterministic, not model-generated."""

    def __init__(self, model: str = "mock-model") -> None:
        self.model = model

    async def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModel],
        system: str | None = None,
    ) -> LLMResponse[SchemaModel]:
        """Build deterministic structured output for supported workflow schemas."""
        del system
        started = time.perf_counter()
        try:
            if schema is ResearchPlan:
                output = schema.model_validate(self._make_plan(prompt))
            elif schema is AnalysisResult:
                output = schema.model_validate(self._make_analysis(prompt))
            elif schema is ReporterOutput:
                output = schema.model_validate(self._make_report(prompt))
            else:
                raise LLMError(f"Mock provider does not support schema: {schema.__name__}")
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Mock provider could not produce {schema.__name__}: {exc}") from exc
        return LLMResponse[SchemaModel](
            output=output,
            model=self.model,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )

    async def generate_text(
        self,
        prompt: str,
        system: str | None = None,
    ) -> LLMResponse[str]:
        """Return a stable, clearly identified offline response."""
        del system
        started = time.perf_counter()
        text = (
            "Deterministic mock response. No external model or network was used. "
            f"Input: {prompt.strip()[:500]}"
        )
        return LLMResponse[str](
            output=text,
            model=self.model,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )

    @staticmethod
    def _make_plan(prompt: str) -> dict[str, Any]:
        task = prompt.lower()
        steps: list[dict[str, Any]] = []

        if any(word in task for word in ("csv", "sales", "revenue")):
            steps.append(
                {
                    "description": (
                        "Aggregate revenue by region from the registered sales dataset."
                    ),
                    "tool_name": "csv_reader",
                    "tool_args": {
                        "operation": "aggregate",
                        "filename": "sales_2025.csv",
                        "group_by": ["region"],
                        "metric_column": "revenue",
                        "agg": "sum",
                    },
                    "depends_on": [],
                }
            )
        if any(word in task for word in ("policy", "document", "target")):
            steps.append(
                {
                    "description": (
                        "Search local policy and target documents for relevant evidence."
                    ),
                    "tool_name": "document_search",
                    "tool_args": {"query": MockLLMProvider._search_query(task), "top_k": 5},
                    "depends_on": [],
                }
            )
        if any(word in task for word in ("compute", "growth", "percent", "percentage", "change")):
            steps.append(
                {
                    "description": (
                        "Calculate the requested change using numeric values returned by prior "
                        "tool results; substitute only collected values."
                    ),
                    "tool_name": "calculator",
                    "tool_args": {},
                    "depends_on": list(range(len(steps))),
                }
            )
        if not steps:
            steps.append(
                {
                    "description": "Search local documents for evidence related to the task.",
                    "tool_name": "document_search",
                    "tool_args": {"query": prompt.strip()[:500] or "research task", "top_k": 5},
                    "depends_on": [],
                }
            )
        return {"steps": steps}

    @staticmethod
    def _search_query(task: str) -> str:
        terms = re.findall(r"[a-z0-9]+", task)
        return " ".join(terms[:12]) or "policy target"

    @staticmethod
    def _make_analysis(prompt: str) -> dict[str, Any]:
        parsed = MockLLMProvider._extract_named_json(prompt, "tool results:")
        tool_results = parsed.get("tool_results", []) if parsed else []
        if parsed and isinstance(parsed.get("tool_results"), list):
            tool_results = parsed["tool_results"]
        elif parsed and isinstance(parsed.get("results"), list):
            tool_results = parsed["results"]

        findings: list[dict[str, Any]] = []
        source_conflicts: list[str] = []
        for index, item in enumerate(tool_results):
            if not isinstance(item, dict):
                continue
            result_data = item.get("data", {})
            if isinstance(result_data, dict):
                conflicts = result_data.get("source_conflicts", [])
                if isinstance(conflicts, list):
                    source_conflicts.extend(
                        str(conflict).strip()
                        for conflict in conflicts
                        if isinstance(conflict, str) and conflict.strip()
                    )
            if not item.get("success", item.get("ok", False)):
                continue
            call_id = item.get("tool_call_id") or item.get("id") or f"mock-tool-call-{index + 1}"
            tool_name = str(item.get("tool_name", "local tool"))
            if isinstance(result_data, dict) and "results" in result_data:
                observed_count = len(result_data.get("results") or [])
                detail = f"returned {observed_count} matching document chunk(s)"
            elif isinstance(result_data, dict) and isinstance(result_data.get("result"), list):
                observed_count = len(result_data["result"])
                detail = f"returned {observed_count} result row(s)"
            else:
                detail = "returned a successful result"
            findings.append(
                {
                    "statement": f"The {tool_name} tool {detail}.",
                    "evidence_refs": [
                        {
                            "reference": str(call_id),
                            "citation": f"Successful {tool_name} tool result",
                        }
                    ],
                    "confidence": 0.7,
                    "source_tool_call_ids": (
                        [str(call_id)] if MockLLMProvider._is_uuid(call_id) else []
                    ),
                }
            )
        summary = (
            f"Analyzed {len(findings)} successful tool result(s)."
            if findings
            else "No successful tool results were provided; no factual findings were generated."
        )
        return {
            "summary": summary,
            "findings": findings,
            "recommendations": (
                ["Review the cited tool results before making decisions."] if findings else []
            ),
            "limitations": (
                ([] if findings else ["The analysis has no successful tool-result evidence."])
                + [f"Source conflict: {conflict}" for conflict in dict.fromkeys(source_conflicts)]
            ),
        }

    @staticmethod
    def _make_report(prompt: str) -> dict[str, Any]:
        parsed_analysis = MockLLMProvider._extract_named_json(prompt, "analysis:")
        if parsed_analysis and isinstance(parsed_analysis.get("analysis"), dict):
            analysis = parsed_analysis["analysis"]
        elif parsed_analysis and isinstance(parsed_analysis.get("findings"), list):
            analysis = parsed_analysis
        else:
            analysis = MockLLMProvider._make_analysis(prompt)
        findings = analysis.get("findings", [])
        refs = [
            {
                "reference": str(reference.get("reference", "")),
                "citation": str(reference.get("citation", "")),
            }
            for finding in findings
            for reference in finding.get("evidence_refs", [])
            if isinstance(reference, dict)
        ]
        return {
            "title": "ResearchPilot Research Report",
            "executive_summary": str(analysis.get("summary", "No analysis summary was provided.")),
            "sections": [
                {
                    "heading": "Evidence-backed findings",
                    "body": "\n".join(
                        str(finding.get("statement", ""))
                        for finding in findings
                        if isinstance(finding, dict)
                    )
                    or "No evidence-backed findings were produced.",
                    "evidence_refs": refs,
                }
            ],
            "findings": [
                {
                    "statement": str(finding.get("statement", "")),
                    "evidence_refs": [
                        reference
                        for reference in finding.get("evidence_refs", [])
                        if isinstance(reference, dict)
                    ],
                }
                for finding in findings
                if isinstance(finding, dict) and finding.get("statement")
            ],
            "recommendations": analysis.get("recommendations", []),
            "limitations": analysis.get("limitations", []),
            "appendix_tables": [],
        }

    @staticmethod
    def _extract_named_json(prompt: str, marker: str) -> dict[str, Any] | None:
        """Parse the JSON object following a prompt's named section, if present."""
        lower_prompt = prompt.lower()
        start = lower_prompt.find(marker.lower())
        candidates = [prompt[start + len(marker) :].strip()] if start >= 0 else []
        candidates.append(prompt.strip())
        for candidate in candidates:
            try:
                value, _ = json.JSONDecoder().raw_decode(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _is_uuid(value: Any) -> bool:
        try:
            UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return False
        return True
