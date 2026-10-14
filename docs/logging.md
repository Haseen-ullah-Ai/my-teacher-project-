# Logging and metrics

## Structured logs

The backend configures structlog for structured output. A request middleware accepts `X-Request-ID` or creates a UUID, binds it to the current log context, and echoes it in the response header.

`RunLogger` is run-bound. Its `info`, `warn`, `error`, and `debug` methods emit structured stdout logs and queue database `ExecutionLog` rows. Writes are batched and flushed when the batch limit is reached, at graph-node boundaries, and during shutdown. `flush()` also updates the run status in the same database transaction. The logger verifies that compatibility node events use the matching run id.

Sensitive data is recursively redacted for keys matching `key`, `token`, `password`, or `secret`, and secret-like strings (API key assignments, bearer strings, common `sk-` credentials). Numeric token-count fields remain numeric. LLM calls log provider/model, latency, prompt SHA-256, and token counts if known. Raw prompts are excluded by default; `LOG_LLM_PROMPTS=true` opts in to logging prompts and should only be used in controlled development.

## Event catalog

| Event | Meaning | Current status |
|---|---|---|
| `node_started` | Instrumented graph node entered. | Emitted by the common node wrapper. |
| `node_finished` | Node returned successfully; includes duration. | Emitted by the common node wrapper. |
| `node_failed` | Node raised; includes exception type/message and duration. | Emitted by the common node wrapper before re-raising. |
| `node_transition` | Compatibility lifecycle event with graph node/status. | Emitted by stub node transition helper. |
| `llm_call` | Provider/model, latency, prompt hash, token metadata. | Logger method available; stub graph nodes do not invoke the LLM. |
| `tool_call_started` / `tool_call_finished` | Tool attempt lifecycle. | Emitted by the executor stub as synthetic success; no registry call or `tool_calls` row is made. |
| `tool_call_failed` | Failed tool attempt. | Planned; executor node does not call tools. |
| `retry_scheduled` / `fallback_applied` | Retry/backoff or fallback decision. | Recovery stub emits these only when corresponding state flags are set; no real retry or fallback is performed. |
| `replan_triggered` | Validation-driven plan retry. | Stub validator can emit this for a failing state, but does not perform validation. |
| `validation_check` | Per-check pass/fail/warning detail. | Stub emits one `stub_validation` check event only. |
| `run_completed` / `run_failed` | Run terminal outcome. | Stub reporter emits completion; failure lifecycle logging is in runner/error handling. |

Graph node names are normalized to the database's allowed node set; tool selection, execution, collection, and recovery events are stored as node `executor`.

## Prometheus metrics

`GET /metrics` returns Prometheus text exposition. Current metric definitions:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `researchpilot_runs_total` | Counter | `status` | Run terminal outcomes. |
| `researchpilot_tool_calls_total` | Counter | `tool`, `status` | Tool attempts by tool and result. |
| `researchpilot_tool_duration_seconds` | Histogram | `tool` | Tool runtime. |
| `researchpilot_run_duration_seconds` | Histogram | none | Run runtime. |
| `researchpilot_retries_total` | Counter | none | Scheduled retries. |

Metric definitions and render endpoint exist. The stub executor increments a successful tool counter/duration with a synthetic zero-duration tool call; this is not evidence of actual tool execution. Run counters/durations are updated by the runner lifecycle.

## Querying persisted execution history

After a database-backed run exists, inspect its chronological story with:

```sql
SELECT node, event, level, message, data, created_at
FROM execution_logs
WHERE run_id = '00000000-0000-0000-0000-000000000000'
ORDER BY id;
```

Replace the UUID with a real `research_runs.id`. The current API has no log-query route; query PostgreSQL directly.
