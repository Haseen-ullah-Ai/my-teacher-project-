# Sample run: current stub workflow

> **Important:** this is an example of the current graph scaffold, not a successful evidence-backed research result. Stage 7/8 behavior is not implemented in the graph nodes, and no `/api/v1/runs` endpoint exists. Do not treat the sample report below as business analysis.

## Task

“Analyze Q3 sales by region, compare to the targets, and recommend actions.”

## Stub plan

The planner currently returns this one-step placeholder (the original task is passed through as the query):

```json
[
  {
    "index": 0,
    "description": "Stub data-gathering step for graph execution.",
    "tool_name": "document_search",
    "tool_args": {
      "query": "Analyze Q3 sales by region, compare to the targets, and recommend actions",
      "top_k": 1
    }
  }
]
```

## What currently happens

`AgentRunner.run(task)` creates a `research_runs` row with `pending` status, initializes a state object, and schedules the compiled graph. Each node is wrapped by instrumentation that logs `node_started`, `node_finished`, and flushes at node boundaries.

The graph topology routes through:

1. **Intake:** records the original task as the objective and adds a generic expected output.
2. **Planner:** creates a fixed one-step placeholder plan using `document_search`; it does not ask the LLM to plan.
3. **Tool loop:** selection chooses that step, but the executor does not call the registry. It fabricates a successful stub result, and collection adds a `stub:step:0` reference to in-memory state. No `tool_calls` row is written.
4. **Analyzer:** a stub status transition and empty analysis; it does not produce findings.
5. **Validator:** returns a passing placeholder validation result.
6. **Reporter:** creates a placeholder `ReportDraft`, marks the run completed, and logs `run_completed`.

## Representative log story

Event names and messages below reflect current node-wrapper/stub source behavior. This is a representative trace, not a captured database query; exact timestamps, durations, and row IDs vary by execution.

```text
intake   INFO node_transition  Task accepted for research.
planner  INFO node_transition  Created a one-step stub research plan.
executor INFO node_transition  Selected plan step 0.
executor INFO tool_call_started Stub tool call started. (tool=document_search)
executor INFO node_transition  Stub tool execution completed successfully.
executor INFO tool_call_finished Stub tool call finished successfully. (stub result)
executor INFO node_transition  Collected the current step result.
executor INFO node_transition  Selected plan step 1. (routes to analysis)
analyzer INFO node_transition  Stub analysis node completed.
validator INFO validation_check Stub validation passed.
reporter INFO node_transition  Stub report generation started.
reporter INFO run_completed    Research run completed.
```

The common wrapper additionally emits `node_started`/`node_finished` around each node. The stored `ExecutionLog.node` value normalizes tool-loop node names to `executor`. Actual rows, timestamps, and IDs require PostgreSQL and vary by execution. The DB run id can be used to inspect persisted events with the query in [logging](logging.md).

## Current placeholder report

The reporter's actual stub draft has this content:

- **Title:** ResearchPilot Stub Report
- **Executive summary:** This report confirms the agent graph completed its stub workflow.
- **Sections:** none
- **Findings:** none
- **Recommendations:** none
- **Limitations:** Stage 6 graph nodes are stubs; no real tool execution occurred.

It does not include CSV findings, target comparisons, numeric calculations, or evidence citations. The sample CSV and policy documents can be used to test the standalone CSV and document-search tools after database seeding, but the agent does not currently combine those results into a report.

The stub reporter places this `ReportDraft` in the graph state only. It does not call the `report_generator` tool or persist a `reports` row.

## Expected future behavior

Once the executor and analysis stages are implemented, this task should create a plan using `csv_reader`, `document_search`, and `calculator`, cite real dataset/document provenance, validate numeric derivations and source conflicts, and render a report. That future output must be captured from a real run before replacing this stub-focused example.
