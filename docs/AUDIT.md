# ResearchPilot Stage 16 Release Audit

**Audit date:** 2026-10-07  
**Release decision:** **NO-GO**  
**Scope:** Workspace contents and observable local build/runtime behavior. The requested `.github/copilot-instructions.md` is absent, and this workspace has no `.git` directory or available Git executable; therefore the audit uses the Stage 16 checklist and repository documentation as its review criteria, but cannot verify Git history, commit state, or release tags.

## Executive summary

Several foundations are present: the local tool registry, typed graph state and topology, a deterministic no-network mock provider, PostgreSQL persistence models, structured run logging, Docker startup migrations and seeding, and a React dashboard shell. However, the agent nodes that turn those foundations into research are still explicit stubs, and the FastAPI application mounts no `/api/v1` research routes. The frontend therefore cannot start or observe an actual task. This is a release blocker, not a limitation that can be fixed by documentation.

During this audit, the vulnerable frontend toolchain was updated to patched, exactly pinned versions; Tailwind was migrated to v4; a Python environment lockfile was generated; and Python CLI output was changed to avoid `print()` calls. These changes passed the checks listed below. The core research flow, UI-to-API lifecycle, and Git release requirements remain unmet.

## Requirement and quality-gate results

| Checklist item | Result | Evidence / notes |
|---|---|---|
| Understand and parse the user's research task | **FAIL** | [intake.py](../backend/app/agent/nodes/intake.py#L13) copies the task into a stub `ParsedTask`; it does not call the LLM or enforce task limits/scope. |
| Plan research steps | **FAIL** | [planner.py](../backend/app/agent/nodes/planner.py#L13) creates a constant, one-step plan. It does not validate tools/arguments/dependencies or replan. |
| Select and call registered tools | **FAIL** | [select_tool.py](../backend/app/agent/nodes/select_tool.py#L12) only logs a transition; [execute_tool.py](../backend/app/agent/nodes/execute_tool.py#L13) records a fabricated successful result and never calls `ToolRegistry.get(...).execute(...)`. No real tool-call rows are produced by this path. |
| Collect information and trustworthy evidence | **FAIL** | [collect.py](../backend/app/agent/nodes/collect.py#L13) creates `stub:step:*` evidence rather than resolving a persisted tool call or source chunk. |
| Analyze gathered evidence | **FAIL** | [analyzer.py](../backend/app/agent/nodes/analyzer.py#L13) returns an empty stub analysis. |
| Validate the result | **FAIL** | [validator.py](../backend/app/agent/nodes/validator.py#L13) defaults to passing validation with no checks; the deterministic checks and LLM rubric are absent. |
| Generate and persist a structured report | **FAIL** | [reporter.py](../backend/app/agent/nodes/reporter.py#L13) returns a placeholder report; it does not call the report tool or persist a report. |
| Execution logs | **PARTIAL** | [RunLogger](../backend/app/services/run_logger.py#L44) supports structured events, redaction, batching, and flush; [common.py](../backend/app/agent/nodes/common.py#L30) instruments stub node boundaries. Tool attempts and meaningful evidence lineage are not logged because tool execution is stubbed. |
| Versioned public API and UI lifecycle | **FAIL** | [create_app](../backend/app/main.py#L42) mounts only `/health` and `/metrics`; [routes.py](../backend/app/api/routes.py#L12) is a legacy, unmounted `/api` router. Requests to `/api/v1/runs`, `/api/v1/datasets`, and `/api/v1/documents` returned 404. |
| Local-only tools; offline mock | **PARTIAL** | The registered tool layer is local and constrained ([registry.py](../backend/app/tools/registry.py#L51)); [MockLLMProvider](../backend/app/llm/providers/mock_provider.py#L16) is deterministic and does not use the network. Optional OpenAI/Anthropic adapters are network clients by design, but are not needed by the mock. Because task execution and the public API are incomplete, the **application does not work fully offline end to end**. |
| Secrets, dynamic evaluation, TODOs, and console output | **PASS WITH SCOPE** | A source scan found no embedded credential patterns; its sole credential-shaped match is a deliberately fake redaction-test fixture in `backend/tests/unit/test_run_logger.py`. No Python `eval()`/`exec()` calls or TODO/FIXME markers were found in application, test, evaluation, or script sources; the calculator uses an AST allowlist. Python CLI `print()` calls were replaced with logger/stdout writes. |
| Unused imports and code hygiene | **PARTIAL** | Ruff passed on `app`, tests, evaluations, and scripts, including unused-import checks. This does not prove that all unreferenced modules or functions across the full repository are dead-code-free. |
| Clean-volume quick-start | **PARTIAL** | A separate Compose project with newly created volumes started PostgreSQL, backend, and frontend; the backend and UI health checks returned healthy/HTTP 200. Only the isolated test project's volumes were removed; the existing local volumes were preserved. The sample task could not be submitted because its API is absent. |
| Responsive UI | **PARTIAL** | The dashboard had no horizontal document overflow at 375px, 768px, or 1440px. This did not cover every route or a live run-detail view (no run can be created). |
| Dark theme | **PASS, SMOKE TEST** | Toggling the theme changed the root `data-theme` from `light` to `dark` and persisted the preference. |
| Keyboard navigation | **NOT VERIFIED** | The UI uses native buttons and links with accessible labels, but a full keyboard-only flow was not completed. |
| Lighthouse accessibility >= 90 | **NOT VERIFIED** | Lighthouse was not installed/run. No score is claimed. |
| No browser-console errors | **FAIL** | Dashboard/new-research requests to missing `/api/v1` routes return 404. |
| Mock task <15s and read API p95 <200ms | **PARTIAL / FAIL** | Forty local sequential samples measured `/health` p95 at 93.29ms and `/metrics` p95 at 35.94ms. These are the only mounted reads; business read endpoints and the end-to-end task endpoint are absent, so the specified application p95 and task duration cannot be assessed. |
| Dependency pins and lockfiles | **PASS, WORKSPACE STATE** | Python direct dependencies are exact-pinned in `backend/requirements.txt` and `backend/requirements-dev.txt`; `backend/requirements-lock.txt` records the validated environment. Frontend direct dependencies are exact-pinned in `frontend/package.json`, with `frontend/package-lock.json`. A repository without Git metadata cannot establish that any file is committed. |
| Python dependency integrity | **PASS** | `pip check`: no broken requirements found. |
| Frontend vulnerabilities | **PASS AFTER FIX** | `npm audit`: zero vulnerabilities. Vitest was upgraded to 4.1.11 and Tailwind to 4.3.3; both frontend tests and production build passed after migration. |
| `.gitignore` | **PASS BY INSPECTION** | Ignores local environments, `.env` files except `.env.example`, caches, build outputs, reports, logs, and generated evaluation JSON. Commit behavior could not be checked. |
| Meaningful Git history and release tag `v1.0.0` | **BLOCKED / FAIL** | No `.git` directory and no `git` executable are present. History cannot be inspected and a tag cannot be created or validated from this workspace. |

## Agent skills: implementation status and locations

| Skill / capability | Implementation location | Audit status |
|---|---|---|
| Agent state | [state.py](../backend/app/agent/state.py#L22), [models.py](../backend/app/agent/models.py#L23) | State and Pydantic data shapes exist; current node behavior does not populate them with real research results. |
| Tool calling | [registry.py](../backend/app/tools/registry.py#L12), [base.py](../backend/app/tools/base.py#L36) | Registry and typed/timeout-wrapped tools exist; the graph executor does not invoke them. |
| Planning | [planner.py](../backend/app/agent/nodes/planner.py#L13), [mock_provider.py](../backend/app/llm/providers/mock_provider.py#L57) | Mock plan generation exists independently; graph planner remains a fixed stub. |
| Memory/context | [state.py](../backend/app/agent/state.py#L36), [models.py](../backend/app/agent/models.py#L90), [collect.py](../backend/app/agent/nodes/collect.py#L13) | Scratch-fact shapes exist; current collection stores only synthetic results. |
| Retry and fallback | [graph.py](../backend/app/agent/graph.py#L49), [retry_or_fallback.py](../backend/app/agent/nodes/retry_or_fallback.py#L13) | Conditional route logic and event logging exist; no tool error drives real retries, argument repair, fallback, or backoff execution. |
| Failure handling | [runner.py](../backend/app/agent/runner.py#L215) | Runner catches run failures, persists terminal state, flushes logs, and re-raises; per-tool criticality/circuit-breaker behavior is not implemented. |
| Validation | [validator.py](../backend/app/agent/nodes/validator.py#L13), [graph.py](../backend/app/agent/graph.py#L89) | Replan route exists; validation is stubbed and always passes by default. |
| Execution logging | [run_logger.py](../backend/app/services/run_logger.py#L44), [common.py](../backend/app/agent/nodes/common.py#L30) | Structured, redacted, persisted node logging exists; instrumentation cannot report real tool/LLM execution until the nodes are implemented. |
| LangGraph topology | [graph.py](../backend/app/agent/graph.py#L103) | Nodes/edges compile, but functional completion is not demonstrated. |

## Verification performed

- Backend: **79 passed, 6 skipped**, coverage **86.45%**; Ruff passed; strict mypy passed; `pip check` passed; deterministic eval harness **10/10**.
- Frontend: lint, TypeScript check, **8 tests**, and production build passed after the dependency updates.
- Frontend: `npm audit` reported **0 vulnerabilities** after the updates.
- Containers: backend and frontend images rebuilt. A clean, isolated Compose volume set reached healthy status; `/health` returned `{"status":"ok","db":"ok"}` and the UI returned HTTP 200. The user's original volumes were not deleted.
- Locked backend runtime: `pip check` inside the rebuilt Linux/Python 3.11 image reported no broken requirements; the clean-volume startup applied both migrations and ingested 8 documents and 4 datasets.
- API smoke test: `/api/v1/runs`, `/api/v1/datasets`, and `/api/v1/documents` returned 404.
- Browser: dashboard document width matched viewport at 375/768/1440px; a missing API endpoint still emitted a browser-console 404.
- GitHub Actions were not run from this workspace; there is no local Git repository/remote context.

## Release-blocking work

1. Implement the real intake/planner/tool selection/execution/collection/retry/fallback and replan loop; persist each tool attempt and use real source/tool-call evidence.
2. Implement evidence-grounded analysis, deterministic validation, report generation/persistence, and accurate warning/failure statuses.
3. Mount and test the `/api/v1` lifecycle, document/dataset endpoints, SSE, report downloads, rate/concurrency controls, and error envelopes; connect the UI to these routes.
4. Run the end-to-end UI flow, keyboard-only review, full responsive route review, Lighthouse accessibility audit, sample-task duration, and read-endpoint p95 after the API exists.
5. Restore or initialize Git metadata in the intended repository, inspect the staged diff and meaningful history, run CI, then create and verify `v1.0.0` only after the release blockers close.

## Three-minute reviewer demo script

This script demonstrates the currently working shell and local setup only. Do **not** present a completed research report as functional; task execution is not implemented.

1. Start the app with `docker compose up --build` and wait for all three services to report healthy.
2. Open `http://localhost:3000`, show the dashboard shell and its backend-connected status.
3. Resize the browser to mobile width and then tablet/desktop width to show the responsive shell.
4. Switch between light and dark themes and open Settings to show the configured API URL and local-first boundary.
5. Open New Research and show the task form and example prompt; explain that submit currently lacks a mounted API endpoint.
6. Show [the agent graph diagram](agent_graph.mmd), [this audit](AUDIT.md), and the health endpoint at `http://localhost:8000/health`; close by stating the specific release blockers above.
