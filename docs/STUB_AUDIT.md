# ResearchPilot Stub and Placeholder Audit

**Audit date:** 2026-10-08  
**Scope:** repository source and wiring relevant to the ResearchPilot agent, its database persistence, versioned API, and frontend run display. No application code was changed for this audit.

## Repository instructions

The requested `.github/copilot-instructions.md` file does not exist in this checkout. The `.github` directory contains workflows, templates, Dependabot configuration, and CODEOWNERS, but no Copilot instructions file. Therefore this audit is based on the product and architecture requirements already supplied for this project; it could not validate compliance against that missing file.

## Summary

The API can create a persisted run and the graph can finish, but the graph's agent nodes are still topology-testing stubs. In particular, the current `intake -> planner -> execute_tool -> collect -> analyzer -> validator -> reporter` path does not classify intent, call a registered tool, perform analysis, or persist a report. Consequently, greetings and arithmetic are handled as research, with no user-facing answer. The intended visible-answer feature (`result_type` and `answer_text`) is absent from the state, database model, response schemas, and migrations.

## Stub, placeholder, and hard-coded behavior

| File | What it does now | What it must do |
|---|---|---|
| `backend/app/agent/nodes/intake.py` | Copies the request into `ParsedTask.objective`, leaves entities and constraints empty, and assigns a fixed “evidence-backed research report” output. It performs no intent classification and does not consult the LLM. | Classify research, calculation, smalltalk, out-of-scope, and too-vague requests; provide the appropriate next action/context and route non-research requests away from research tools. |
| `backend/app/agent/nodes/planner.py` | If no plan exists, emits exactly one hard-coded `document_search` step, regardless of task. | Use the configured LLM/planning policy to produce a task-appropriate plan using available local tools and user-selected source scope. |
| `backend/app/agent/nodes/select_tool.py` | Emits a transition log only. It does not validate or select a registry tool. | Resolve and validate the next planned tool and its typed input before execution. |
| `backend/app/agent/nodes/execute_tool.py` | Marks a step successful, returns `{"message": "stub tool output"}`, logs duration `0`, and records a successful metric. It never calls `deps.tool_registry` or persists a `ToolCall`. | Execute the selected registered tool with validated arguments; persist its input, output/error, status, attempt, and duration; propagate real results and typed failures. |
| `backend/app/agent/nodes/collect.py` | Builds a `ToolExecutionResult` around the fake pending result and fabricates evidence IDs such as `stub:step:0` with source type `stub_tool_call`. | Collect actual tool outputs, attach evidence tied to persisted tool calls and source records, and update agent memory with sourced facts. |
| `backend/app/agent/nodes/analyzer.py` | Always writes the fixed summary “Stub analysis completed; no factual conclusions were generated.” with no findings. It does not invoke the LLM. | Analyze collected results, produce concise supported findings and recommendations, preserve citations, and produce a direct answer for calculation/conversation/refusal/clarification intents as appropriate. |
| `backend/app/agent/nodes/validator.py` | Logs `stub_validation`; when there is no validation in state, creates `ValidationResult(passed=True, checks=[])`. No meaningful check is performed. | Run evidence, citation, consistency, and output-shape checks; persist checks and fail/warn when the output does not meet policy. |
| `backend/app/agent/nodes/retry_or_fallback.py` | Logs retry/fallback requests and increments retry metrics, but performs no wait/backoff and does not itself establish valid retry/skip decisions. Because the executor always reports success, the failure path is not exercised by normal graph execution. | Apply bounded retry/fallback behavior to actual tool failures, honoring configured retry limits and backoff, recording attempts and outcomes. |
| `backend/app/agent/nodes/reporter.py` | Returns a literal “ResearchPilot Stub Report”, empty sections/findings/recommendations, and a limitation that the nodes are stubs. It marks the run completed without persisting a `Report` row. | Render the validated analysis into a structured report, persist it, link it to the run, and include the appropriate visible response. |
| `backend/app/agent/graph.py` | Wires the intended node topology, but its docstring identifies the graph as a stub graph and every registered business node above is currently stubbed. The default checkpointer is `MemorySaver`, not durable PostgreSQL checkpoint storage. | Retain the intended topology while using functional nodes and durable state/checkpoint persistence consistent with the deployment requirements. |
| `backend/app/agent/nodes/common.py` | Provides working node-boundary instrumentation and transition logging. Its module docstring says “stub graph nodes,” but the logging/flush helper itself is not a fake tool implementation. | The instrumentation helper can remain; it should serve functional nodes and report actual execution boundaries. |
| `backend/app/services/research_service.py` | Runs the graph and maps `analysis` into the legacy `ResearchReport`. As its graph nodes are stubs, its summary is the analyzer’s fixed stub summary and its findings/evidence are empty. It does not create a `ResearchRun` row or associate node logs with a persisted run ID. | Either use the persisted run/runner path or persist this legacy task path consistently; return only actual analysis and a visible answer rather than presenting a stub completion. |
| `backend/app/api/routes.py` | `POST /api/tasks` synchronously awaits `ResearchService.run_task` and returns the legacy report schema. It is a real route, but currently exposes the stub graph output. | Preserve its established contract if required, but route execution through functional intent-aware processing and return an honest result. |
| `backend/app/api/v1_routes.py` — `RunCreateRequest` / `create_run` | The request accepts `max_retries`, `max_replans`, `dataset_ids`, and `document_ids`; `create_run` calls only `runner.run(payload.task)`. All four other request values are discarded. | Validate selected IDs and pass source scope and per-run settings through runner input into `AgentState`, planner/tool calls, and persistence. |
| `backend/app/api/v1_routes.py` — `/runs/{run_id}/events` | Returns a one-time JSON list queried from `execution_logs`; it is not an SSE response or a live stream. | Implement a streaming response (or make the frontend poll this JSON endpoint instead), with incremental cursor handling and completion semantics. |
| `backend/app/llm/providers/mock_provider.py` | This is an intentional deterministic offline provider, not a production LLM. Its planner helper uses keyword rules, including a hard-coded `sales_2025.csv` and fixed column/aggregation names. Its analysis helper emits generic “tool returned N…” statements rather than semantic analysis. Current graph nodes do not call this provider at all. | Keep deterministic/offline behavior, but implement deterministic intent and planning behavior for supported test scenarios without assuming dataset names/columns; ensure graph nodes actually use the configured LLM client. |
| `frontend/src/hooks/useRunEvents.ts` and `frontend/src/api/client.ts` | The hook asks for `text/event-stream` and repeatedly reconnects. The current backend events handler returns JSON, so the frontend’s SSE parser receives no SSE event blocks and the request finishes. The successful-response loop waits 500 ms, resets the delay to 500 ms, and reconnects again. | Make backend and frontend agree on SSE versus polling. For SSE, stream encoded events, honor `Last-Event-ID`, and close only at run completion; for polling, use the JSON payload and a bounded polling interval without an SSE parser. |

### Intent and visible answer fields

The requested intent behaviors are not implemented:

| Example request | Current path/result |
|---|---|
| `how are you` | Treated as a research task. `RunCreateRequest.task` accepts it (11 characters), then the one-step planner requests `document_search`; no conversational answer is produced. |
| `12+546` | `POST /api/v1/runs` rejects it because `RunCreateRequest.task` requires at least 10 characters. If sent through the legacy endpoint, the stub planner/executor/analyzer still does not calculate it. |
| `browse google for news` | No out-of-scope classifier exists; it is treated as local document research. |
| `Analyze Q3 sales by region` | No intent classification or source-scope propagation exists; the planner still emits the single fixed document-search step, not a CSV analysis plan. |

`AgentState` has no `intent`, `result_type`, or `answer_text` fields. `ResearchRun` has no `result_type` or `answer_text` columns. `ResearchReport` and the frontend run/report types likewise do not expose those values. The migrations `backend/alembic/versions/0001_initial_schema.py` and `0002_run_metrics.py` do not add them.

## Database write audit

The ORM models and repository methods exist, but no application execution path calls the repository create methods for the five execution-result tables below. Repository definitions alone do not persist rows.

| Table | Current application writes? | Evidence / consequence |
|---|---|---|
| `tool_calls` | **No** | `ToolCallRepository.create()` exists in `backend/app/repositories/research.py`, but there are no application call sites. The executor returns a fabricated result instead. The detail API can query this table, but normal graph runs leave it empty. |
| `plan_steps` | **No** | `PlanStepRepository.create()` exists, but no application call site persists planner output. Plan steps stay in transient graph state; the detail route may fall back to `ResearchRun.plan`, which is not populated by the graph path. |
| `findings` | **No** | `FindingRepository.create()` exists, but no graph/service call site writes analyzed findings. The current analyzer creates none. |
| `validation_results` | **No** | `ValidationResultRepository.create()` exists, but no application call site persists validation attempts. The validator’s in-state empty pass is not stored in this table. |
| `reports` | **No** | `ReportRepository.create()` exists, but reporter does not call it. The run detail query for reports therefore finds none for normal runs. |
| `research_runs` | **Yes, on the versioned run path** | `AgentRunner.run()` creates a pending `ResearchRun`, and terminal handling updates it. The legacy `/api/tasks` service path does not create one. |
| `execution_logs` | **Yes, on the versioned runner path** | `RunLogger` batches and flushes `ExecutionLog` rows; `DatabaseRunLogger` persists node transitions. The legacy service path has no run ID and does not use the persisted runner logger. |
| `documents`, `document_chunks`, `datasets` | **Yes** | Upload routes and `IngestionService` write registered metadata and document chunks. |

The five execution repositories (`PlanStepRepository`, `ToolCallRepository`, `FindingRepository`, `ValidationResultRepository`, `ReportRepository`) are defined in `backend/app/repositories/research.py`; a source-wide application search found no callers of those repository classes outside their definitions/exports. The run detail API reads these tables but does not write them.

## Selected dataset/document scope path

The selected IDs are accepted by the API model but lost before agent execution:

1. `RunCreateRequest` in `backend/app/api/v1_routes.py` declares `dataset_ids` and `document_ids`.
2. `create_run()` calls `await runner.run(payload.task)`, passing only the task string.
3. `AgentRunner.run()` in `backend/app/agent/runner.py` accepts only `task: str`.
4. Its initial `AgentState` contains `run_id`, `task`, plan/results/etc., but no dataset or document IDs.
5. `AgentState` in `backend/app/agent/state.py` has no source-scope fields.

Therefore selected source IDs do not reach the graph, tool registry, tools, or database run record. The request’s `max_retries` and `max_replans` fields are similarly dropped; graph routing uses global `settings` values instead.

## Why the events request closes and the frontend reconnects

The actual route in `backend/app/api/v1_routes.py` is a finite database query returning `list[dict]`. It does not use `StreamingResponse`, does not set `text/event-stream`, and does not wait on the `AgentRunner.stream_events()` queue. It supports an `after_id` query parameter but does not read the `Last-Event-ID` request header.

In contrast, `frontend/src/api/client.ts` sends `Accept: text/event-stream` and parses only SSE blocks separated by blank lines. The JSON array returned by the API is not SSE; the client reaches the end of the response without dispatching an event block and returns. `frontend/src/hooks/useRunEvents.ts` then treats that successful close as a reconnectable connection: it resets `retryDelay` to 500 ms and waits 500 ms before reconnecting. The observed approximately one-second cadence is the short completed request plus this repeated 500 ms delay; normal successful responses do not increase the delay.

Persisted `ExecutionLog` rows do contain run events such as node boundaries and `run_completed` (through `RunLogger`/`DatabaseRunLogger`). The issue is transport: the route reads them as a one-time JSON list, while the frontend expects a long-lived SSE stream.

## Additional API/UI gaps relevant to visible answers

- The frontend calls `/runs/{id}/report`, `/runs/{id}/report/download`, `/runs/{id}/cancel`, `/runs/{id}/retry`, document deletion, and dataset deletion. The current `backend/app/api/v1_routes.py` does not define those routes.
- `/runs/{id}` returns `report: null` for ordinary graph runs because no `Report` is persisted.
- The current frontend API types in `frontend/src/types/api.ts` do not define `result_type` or `answer_text`; the run detail UI has no field from which to display the requested intent-specific answer.
- `/api/v1/tools` is backed by a real `ToolRegistry` and can list the four registered local tools (`document_search`, `csv_reader`, `calculator`, `report_generator`). This registry is not currently invoked by the graph’s stub executor.

## Mock/test code versus runtime stubs

The deterministic `MockLLMProvider` and `FaultInjectingTool` are intentional offline/test mechanisms, not evidence that network access or real tool implementations are inherently missing. The concrete runtime blocker is that graph nodes do not invoke them correctly: planner/analyzer do not call the LLM client, and `execute_tool` does not call the registry. The real implementations for `calculator`, `csv_reader`, `document_search`, and `report_generator` exist under `backend/app/tools/`; they are currently unreachable through the stub graph execution node.

