"""Execute deterministic benchmark tasks against the mock LLM provider."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.schemas import AnalysisResult, ResearchPlan

EVALS_DIR = Path(__file__).resolve().parent
TASKS_PATH = EVALS_DIR / "tasks"
RESULTS_PATH = EVALS_DIR / "results" / "latest.json"


def _load_tasks() -> list[dict[str, Any]]:
    """Load and validate all benchmark YAML files in stable filename order."""
    tasks: list[dict[str, Any]] = []
    for path in sorted(TASKS_PATH.glob("*.yaml")):
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError(f"Benchmark must be a YAML mapping: {path.name}")
        required = {
            "task",
            "expected_tools",
            "expected_findings_keywords",
            "must_cite",
            "should_flag_conflict",
        }
        missing = required - parsed.keys()
        if missing:
            raise ValueError(f"{path.name} is missing required fields: {sorted(missing)}")
        parsed["benchmark"] = path.stem
        tasks.append(parsed)
    if len(tasks) != 10:
        raise ValueError(f"Expected exactly 10 benchmark task files; found {len(tasks)}")
    return tasks


def _fixture_result(tool_name: str, *, conflict: str | None = None) -> dict[str, Any]:
    """Build deterministic, explicitly synthetic tool output for LLM contract checks."""
    tool_call_id = str(uuid4())
    if tool_name == "document_search":
        data: dict[str, Any] = {
            "results": [{"chunk_id": str(uuid4()), "snippet": "Synthetic benchmark evidence."}]
        }
    elif tool_name == "csv_reader":
        data = {
            "result": [{"region": "North", "revenue": 100}],
            "provenance": {"dataset": "synthetic-benchmark.csv", "row_count_scanned": 1},
        }
    elif tool_name == "calculator":
        data = {"value": 12.0, "normalized_expression": "pct_change(100, 112)"}
    else:
        data = {"message": "Synthetic benchmark result."}
    if conflict:
        data["source_conflicts"] = [conflict]
    return {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "success": True,
        "data": data,
    }


async def _evaluate(task: dict[str, Any], client: MockLLMProvider) -> dict[str, Any]:
    """Evaluate planning, finding keywords, citations, and source-conflict limitations."""
    started = time.perf_counter()
    plan_response = await client.generate_structured(str(task["task"]), ResearchPlan)
    plan = ResearchPlan.model_validate(plan_response.output)
    tools_used = list(dict.fromkeys(step.tool_name for step in plan.steps))
    expected_tools = set(task["expected_tools"])
    checks: dict[str, bool] = {
        "expected_tools": expected_tools <= set(tools_used),
    }

    conflict_message = (
        "Benchmark source conflict: synthetic CSV and document values disagree."
        if task["should_flag_conflict"]
        else None
    )
    tool_results = [
        _fixture_result(
            tool_name,
            conflict=conflict_message if tool_name == "document_search" else None,
        )
        for tool_name in tools_used
    ]
    analysis_prompt = (
        f"Task: {task['task']}\n"
        f"Tool results:\n{json.dumps({'tool_results': tool_results}, sort_keys=True)}"
    )
    analysis_response = await client.generate_structured(analysis_prompt, AnalysisResult)
    analysis = AnalysisResult.model_validate(analysis_response.output)
    finding_text = " ".join(finding.statement.lower() for finding in analysis.findings)
    checks["expected_findings_keywords"] = all(
        str(keyword).lower() in finding_text for keyword in task["expected_findings_keywords"]
    )

    valid_evidence_ids = {str(item["tool_call_id"]) for item in tool_results}
    citations_valid = all(
        reference.reference in valid_evidence_ids
        for finding in analysis.findings
        for reference in finding.evidence_refs
    )
    has_findings = bool(analysis.findings)
    checks["citation_coverage"] = (
        has_findings and citations_valid if task["must_cite"] else citations_valid
    )
    conflict_flagged = any(
        limitation.lower().startswith("source conflict:") for limitation in analysis.limitations
    )
    checks["source_conflict"] = conflict_flagged == bool(task["should_flag_conflict"])
    duration_seconds = max(0.0, time.perf_counter() - started)
    return {
        "benchmark": task["benchmark"],
        "task": task["task"],
        "passed": all(checks.values()),
        "checks": checks,
        "tools_used": tools_used,
        "retries": 0,
        "validation_status": "passed" if all(checks.values()) else "failed",
        "duration_seconds": duration_seconds,
    }


async def run_evaluations() -> list[dict[str, Any]]:
    """Run every benchmark without database access or network calls."""
    client = MockLLMProvider()
    results = [await _evaluate(task, client) for task in _load_tasks()]
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "provider": "mock",
                "results": results,
                "passed": sum(result["passed"] for result in results),
                "total": len(results),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return results


def _print_table(results: list[dict[str, Any]]) -> None:
    """Print the benchmark outcomes in a compact terminal table."""
    headers = ("Task", "Passed", "Tools used", "Retries", "Validation", "Duration")
    rows = [
        (
            str(item["benchmark"]),
            "yes" if item["passed"] else "no",
            ",".join(item["tools_used"]) or "-",
            str(item["retries"]),
            str(item["validation_status"]),
            f"{item['duration_seconds']:.3f}s",
        )
        for item in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    sys.stdout.write(
        " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
        + "\n"
    )
    sys.stdout.write("-+-".join("-" * width for width in widths) + "\n")
    for row in rows:
        sys.stdout.write(
            " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
            + "\n"
        )


def main() -> None:
    """Run the mock evaluations, print their table, and fail on any mismatch."""
    results = asyncio.run(run_evaluations())
    _print_table(results)
    passed = sum(item["passed"] for item in results)
    sys.stdout.write(
        f"\n{passed}/{len(results)} passed; results written to {RESULTS_PATH}\n"
    )
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
