
"""Result collector and memory update node."""

from __future__ import annotations

from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import EvidenceRef, ScratchFact, ToolExecutionResult
from app.agent.nodes.common import log_transition
from app.agent.state import AgentState


def _tool_data_payload(data: Any) -> dict[str, Any]:
    """Normalize pending tool data into a dict for ToolExecutionResult."""
    if data is None:
        return {}

    if isinstance(data, dict):
        return data

    return {"value": data}


def _build_evidence(
    tool_name: str,
    step_index: int,
    data: dict[str, Any],
    *,
    success: bool,
) -> list[EvidenceRef]:
    """Derive evidence references only from actual tool output."""
    if not success:
        return []

    if tool_name == "document_search":
        evidence: list[EvidenceRef] = []
        results = data.get("results")

        if not isinstance(results, list):
            return evidence

        for item in results:
            if not isinstance(item, dict):
                continue

            chunk_id = item.get("chunk_id")
            if chunk_id is None:
                continue

            title = str(item.get("document_title", "document"))
            chunk_index = item.get("chunk_index")
            chunk_label = (
                f"chunk {chunk_index}"
                if chunk_index is not None
                else "chunk"
            )

            evidence.append(
                EvidenceRef(
                    evidence_id=f"document_search:chunk:{chunk_id}",
                    source_type="document_chunk",
                    source_id=str(chunk_id),
                    citation=f"{title} ({chunk_label})",
                )
            )

        return evidence

    if tool_name == "csv_reader":
        provenance = data.get("provenance")

        if not isinstance(provenance, dict):
            return []

        dataset = provenance.get("dataset")
        if not dataset:
            return []

        operation = str(data.get("operation", "read"))

        return [
            EvidenceRef(
                evidence_id=(
                    f"csv_reader:dataset:{dataset}:step:{step_index}"
                ),
                source_type="csv_dataset",
                source_id=str(dataset),
                citation=f"CSV dataset {dataset} ({operation})",
            )
        ]

    if tool_name == "calculator":
        expression = (
            data.get("normalized_expression")
            or data.get("expression")
        )

        if not expression:
            return []

        value = data.get("value")
        citation = f"Calculation: {expression}"

        if value is not None:
            citation = f"{citation} = {value}"

        return [
            EvidenceRef(
                evidence_id=(
                    f"calculator:step:{step_index}:{expression}"
                ),
                source_type="calculation",
                source_id=str(expression),
                citation=citation,
            )
        ]

    if tool_name == "report_generator":
        artifact_path = (
            data.get("markdown_path")
            or data.get("pdf_path")
        )

        if not artifact_path:
            return []

        return [
            EvidenceRef(
                evidence_id=(
                    f"report_generator:artifact:{step_index}"
                ),
                source_type="report_artifact",
                source_id=str(artifact_path),
                citation=f"Generated report artifact at {artifact_path}",
            )
        ]

    return []


def _deduplicate_evidence(
    evidence: list[EvidenceRef],
) -> list[EvidenceRef]:
    """Keep the first evidence reference for each stable evidence ID."""
    unique: dict[str, EvidenceRef] = {}

    for item in evidence:
        unique.setdefault(item.evidence_id, item)

    return list(unique.values())


async def collect(
    state: AgentState,
    deps: AgentDependencies,
) -> dict[str, Any]:
    """Collect the pending tool output into graph state and memory."""
    update = await log_transition(
        state,
        deps,
        "collect",
        "running",
        "Collected the current step result.",
    )

    pending = state.get("pending_result", {})

    if not isinstance(pending, dict):
        raise TypeError("Pending tool result must be an object")

    step_index = int(
        pending.get(
            "step_index",
            state.get("current_step_index", 0),
        )
    )
    tool_name = str(pending.get("tool_name", "unknown"))
    success = bool(pending.get("success", False))
    result_data = _tool_data_payload(pending.get("data"))
    result_error = pending.get("error")

    if result_error is not None and not isinstance(result_error, str):
        raise TypeError("Pending tool result error must be text or null")

    raw_evidence = _build_evidence(
        tool_name,
        step_index,
        result_data,
        success=success,
    )
    evidence = _deduplicate_evidence(raw_evidence)

    collected = ToolExecutionResult(
        tool_name=tool_name,
        step_index=step_index,
        success=success,
        data=result_data,
        error=result_error,
        evidence=evidence,
    )

    update["tool_results"] = [
        *state.get("tool_results", []),
        collected,
    ]
    update["active_evidence"] = evidence
    update["memory"] = [
        *state.get("memory", []),
        ScratchFact(
            key=f"step_{step_index}_result",
            value=collected.data,
            source_refs=evidence,
        ),
    ]
    update["current_step_index"] = step_index + 1

    return update





# """Result collector and memory update node."""

# from __future__ import annotations

# from typing import Any

# from app.agent.dependencies import AgentDependencies
# from app.agent.models import EvidenceRef, ScratchFact, ToolExecutionResult
# from app.agent.nodes.common import log_transition
# from app.agent.state import AgentState


# def _tool_data_payload(data: Any) -> dict[str, Any]:
#     """Normalize pending tool data into a dict for ToolExecutionResult."""
#     if data is None:
#         return {}
#     if isinstance(data, dict):
#         return data
#     return {"value": data}


# def _build_evidence(
#     tool_name: str,
#     step_index: int,
#     data: dict[str, Any],
#     *,
#     success: bool,
# ) -> list[EvidenceRef]:
#     """Derive evidence references only from actual tool output."""
#     if not success:
#         return []

#     if tool_name == "document_search":
#         evidence: list[EvidenceRef] = []
#         results = data.get("results")
#         if not isinstance(results, list):
#             return evidence
#         for item in results:
#             if not isinstance(item, dict):
#                 continue
#             chunk_id = item.get("chunk_id")
#             if chunk_id is None:
#                 continue
#             title = str(item.get("document_title", "document"))
#             chunk_index = item.get("chunk_index")
#             chunk_label = f"chunk {chunk_index}" if chunk_index is not None else "chunk"
#             evidence.append(
#                 EvidenceRef(
#                     evidence_id=f"document_search:chunk:{chunk_id}",
#                     source_type="document_chunk",
#                     source_id=str(chunk_id),
#                     citation=f"{title} ({chunk_label})",
#                 )
#             )
#         return evidence

#     if tool_name == "csv_reader":
#         provenance = data.get("provenance")
#         if not isinstance(provenance, dict):
#             return []
#         dataset = provenance.get("dataset")
#         if not dataset:
#             return []
#         operation = str(data.get("operation", "read"))
#         return [
#             EvidenceRef(
#                 evidence_id=f"csv_reader:dataset:{dataset}:step:{step_index}",
#                 source_type="csv_dataset",
#                 source_id=str(dataset),
#                 citation=f"CSV dataset {dataset} ({operation})",
#             )
#         ]

#     if tool_name == "calculator":
#         expression = data.get("normalized_expression") or data.get("expression")
#         if not expression:
#             return []
#         value = data.get("value")
#         citation = f"Calculation: {expression}"
#         if value is not None:
#             citation = f"{citation} = {value}"
#         return [
#             EvidenceRef(
#                 evidence_id=f"calculator:step:{step_index}:{expression}",
#                 source_type="calculation",
#                 source_id=str(expression),
#                 citation=citation,
#             )
#         ]

#     if tool_name == "report_generator":
#         artifact_path = data.get("markdown_path") or data.get("pdf_path")
#         if not artifact_path:
#             return []
#         return [
#             EvidenceRef(
#                 evidence_id=f"report_generator:artifact:{step_index}",
#                 source_type="report_artifact",
#                 source_id=str(artifact_path),
#                 citation=f"Generated report artifact at {artifact_path}",
#             )
#         ]

#     return []


# async def collect(state: AgentState, deps: AgentDependencies) -> dict[str, Any]:
#     """Collect the pending tool output into durable graph state and memory."""
#     update = await log_transition(
#         state, deps, "collect", "running", "Collected the current step result."
#     )
#     pending = state.get("pending_result", {})
#     if not isinstance(pending, dict):
#         raise TypeError("Pending tool result must be an object")

#     step_index = int(pending.get("step_index", state.get("current_step_index", 0)))
#     tool_name = str(pending.get("tool_name", "unknown"))
#     success = bool(pending.get("success", False))
#     result_data = _tool_data_payload(pending.get("data"))
#     result_error = pending.get("error")
#     if result_error is not None and not isinstance(result_error, str):
#         raise TypeError("Pending tool result error must be text or null")

#     evidence = _build_evidence(tool_name, step_index, result_data, success=success)
#     collected = ToolExecutionResult(
#         tool_name=tool_name,
#         step_index=step_index,
#         success=success,
#         data=result_data,
#         error=result_error,
#         evidence=evidence,
#     )
#     update["tool_results"] = [*state.get("tool_results", []), collected]
#     update["active_evidence"] = evidence
#     update["memory"] = [
#         *state.get("memory", []),
#         ScratchFact(
#             key=f"step_{step_index}_result",
#             value=collected.data,
#             source_refs=evidence,
#         ),
#     ]
#     update["current_step_index"] = step_index + 1
#     return update
