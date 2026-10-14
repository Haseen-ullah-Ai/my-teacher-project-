
"""Analyze actual results returned by the approved local tools."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import Analysis, Finding
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


def _get(value: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a dictionary or a model object."""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


async def analyzer(
    state: AgentState,
    deps: AgentDependencies,
) -> dict[str, Any]:
    """Build an analysis from collected tool results without inventing facts."""

    update = await log_transition(
        state,
        deps,
        "analyzer",
        "analyzing",
        "Analyzing collected local-tool results.",
    )

    tool_results = state.get("tool_results", [])
    findings: list[Finding] = []
    successful_tools = 0
    failed_tools = 0
    document_matches = 0
    calculation_count = 0

    for result in tool_results:
        tool_name = str(_get(result, "tool_name", "unknown"))
        success = bool(_get(result, "success", False))
        data = _get(result, "data", {})
        evidence = _get(result, "evidence", []) or []

        if not success:
            failed_tools += 1
            continue

        successful_tools += 1

        if not isinstance(data, dict):
            continue

        if tool_name == "calculator":
            value = data.get("value")
            expression = data.get(
                "normalized_expression",
                data.get("expression", "the requested expression"),
            )

            if value is not None:
                findings.append(
                    Finding(
                        statement=f"The calculation {expression} evaluates to {value}.",
                        evidence=evidence,
                        confidence=1.0,
                    )
                )
                calculation_count += 1

        elif tool_name == "document_search":
            matches = data.get("results", []) or []

            for match in matches:
                title = _get(match, "document_title", "Local document")
                snippet = _get(match, "snippet", "")

                if not snippet:
                    continue

                findings.append(
                    Finding(
                        statement=f"From {title}: {snippet}",
                        evidence=evidence,
                        confidence=0.8,
                    )
                )
                document_matches += 1

        elif tool_name == "csv_reader":
            result_data = data.get("result")

            if result_data is not None:
                findings.append(
                    Finding(
                        statement=(
                            "The CSV tool returned this result: "
                            f"{result_data}"
                        ),
                        evidence=evidence,
                        confidence=1.0,
                    )
                )

    if calculation_count:
        summary = (
            f"Completed {calculation_count} calculation(s) using the local "
            "calculator tool."
        )
    elif document_matches:
        summary = (
            f"Found {document_matches} relevant result(s) in local documents. "
            "Review the findings and their supporting evidence."
        )
    elif successful_tools:
        summary = (
            f"Successfully executed {successful_tools} local tool call(s), "
            "but no interpretable findings were produced."
        )
    else:
        summary = (
            "No successful tool results were available for analysis. "
            "Check the tool execution errors."
        )

    update["analysis"] = Analysis(
        summary=summary,
        findings=findings,
        insights=[],
        risks=(
            ["One or more tool executions failed."]
            if failed_tools
            else []
        ),
        recommendations=(
            ["Add relevant local documents or datasets if more evidence is needed."]
            if not document_matches and not calculation_count
            else []
        ),
    )

    return update






# """Stub analysis node."""

# from __future__ import annotations

# from typing import Any

# from app.agent.dependencies import AgentDependencies
# from app.agent.models import Analysis
# from app.agent.nodes.common import log_transition
# from app.agent.state import AgentState


# async def analyzer(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
#     """Create an empty but valid analysis for a stub graph run."""
#     update = await log_transition(
#         state, deps, "analyzer", "analyzing", "Stub analysis node completed."
#     )
#     update["analysis"] = Analysis(
#         summary="Stub analysis completed; no factual conclusions were generated.",
#         findings=[],
#     )
#     return update
