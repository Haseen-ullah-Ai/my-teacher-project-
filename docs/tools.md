# Controlled tools

All tools are registered explicitly by `build_default_registry()`. `BaseTool.execute()` validates input and output with Pydantic models, enforces a timeout, and returns a common `ToolResult` envelope. Tool failures are returned with typed `error_type` and `error_message` fields. The graph's current executor node is a stub, so these tools are currently callable independently but are not yet used for a full research run.

The registry exposes each tool's name, description, timeout, and JSON input/output schemas. In code these schemas are in `backend/app/tools/schemas.py`.

## Common result envelope

```json
{
  "ok": true,
  "data": {},
  "error_type": null,
  "error_message": null,
  "duration_ms": 12,
  "metadata": {"tool_name": "calculator"}
}
```

An unsuccessful call has `ok: false`, typed error details, and duration. Input schema errors become `ToolInputError`; timeout becomes `ToolTimeoutError`; unexpected execution or invalid output becomes `ToolExecutionError`. Tools may raise these typed errors internally. The current base wrapper normalizes them into `ToolResult`.

## `document_search`

Searches ingested text chunks in PostgreSQL using built-in full-text search. It does not search the public web.

**Input**

| Field | Type | Constraints/default |
|---|---|---|
| `query` | string | Required, 1–500 characters |
| `top_k` | integer | 1–20; default 5 |
| `document_filter` | string or null | Optional; if present 1–500 characters |

**Output data:** `{results: [{chunk_id, document_title, snippet, rank_score, chunk_index}]}`. An empty results list is a successful query. Snippets are bounded to 500 characters. Citation provenance is the returned chunk UUID (`chunk_id`).

**Timeout:** 20 seconds. Requires an injected asynchronous database session. Database failures are surfaced as tool execution errors.

## `csv_reader`

Provides bounded preview and analysis operations over a registered, checksum-matched CSV located under `<DATA_DIR>/csv`. The file must be registered in PostgreSQL before it can be read. The tool resolves paths and rejects traversal outside its configured CSV directory.

**Common input fields**

| Field | Type | Constraints/default |
|---|---|---|
| `operation` | enum | `describe`, `head`, `filter`, `aggregate`, `top_n` |
| `filename` | string | Required, 1–500 characters; registered filename |
| `n` | integer | 1–200; default 10 |
| `column` | string or null | Column used by filter/top_n |
| `operator` | enum or null | `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `in`, `contains` |
| `value` | JSON value | Required for filter; `in` requires a list |
| `group_by` | string array | Maximum 10 group columns |
| `metric_column` | string or null | Aggregate metric, except for `count` |
| `agg` | enum or null | `sum`, `mean`, `min`, `max`, `count`, `median` |
| `ascending` | boolean | Default false |

**Operation behavior**

- `describe`: column names/types, row count, null counts.
- `head`: first `n` rows.
- `filter`: one requested predicate; requires `column`, `operator`, and a non-null value (except list-valued `in`).
- `aggregate`: grouped aggregation, requires `agg`; non-count operations require `metric_column`.
- `top_n`: rows ordered by `column`; requires that column.

**Output data:** `{operation, result, provenance}`. Result rows are capped at 200. Provenance includes dataset filename, rows scanned, and applied filters. For exact CSV row provenance, the current tool reports scan-level provenance rather than stable row ranges; the final evidence-linked agent flow is not implemented yet.

**Timeout:** 30 seconds. Missing file, unregistered dataset, invalid columns, and invalid operation arguments are input errors; changed on-disk checksum and runtime issues are execution errors. An injected asynchronous database session is required.

Ingestion enforces a 2 MiB maximum for `.txt`/`.md` documents and a 10 MiB maximum for `.csv` datasets before reading file contents. The HTTP upload API is not implemented yet; these limits currently apply to files discovered by the local ingestion service.

## `calculator`

Evaluates arithmetic with a restricted Python AST visitor. It does not call `eval()` or execute arbitrary Python.

**Input:** `expression` string, required, 1–1000 characters.

**Supported operators:** `+`, `-`, `*`, `/`, `//`, `%`, and `**`; unary plus/minus.

**Approved functions:** `abs`, `round`, `min`, `max`, `sum`, `sqrt`, `pct_change(old, new)`, `pct_of(part, total)`, and `cagr(start, end, years)`. Exponents are limited in magnitude to 100; AST size is capped at 100 nodes; result magnitude is bounded; non-finite numbers are rejected.

**Output:** `{value, normalized_expression}`.

**Timeout:** 5 seconds. Unsupported AST nodes/functions, invalid arguments, excessive expressions, and division-by-zero conditions return typed errors. The calculator has no database or filesystem access.

## `report_generator`

Renders a structured report draft to Markdown and PDF. The input `ReportDraft` has:

- `title` (1–300 characters), `executive_summary`, and `sections`;
- sections with `heading`, `body`, and optional evidence refs (`reference`, `citation`);
- findings, each with a statement and evidence refs;
- recommendations, limitations, and appendix tables.

Every appendix table requires at least one column and each row must match the column count. Output contains rendered Markdown and the Markdown/PDF output paths.

**Timeout:** 30 seconds. Writes only beneath configured `REPORTS_DIR`. Rendering/filesystem failures are typed tool execution errors.

## Registry extension

Follow [Adding a tool](adding-a-tool.md) to implement schema models, a `BaseTool` subclass, registration, and tests. Keep tools narrowly scoped and do not add network browsing or arbitrary code execution.
