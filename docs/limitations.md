# Current limitations and roadmap

This page prevents design intent from being mistaken for working product behavior.

## Implemented foundations

- Async FastAPI application with `/health`, `/metrics`, CORS, and request correlation id.
- SQLAlchemy models and Alembic migrations for runs, plan steps, tool calls, logs, findings, validations, reports, documents, chunks, and datasets.
- PostgreSQL full-text search schema and ingestion/repository code.
- Four schema-validated local tools and registry; AST calculator avoids `eval`.
- Provider adapters and prompt template assets; mock provider is default.
- LangGraph topology, state, dependencies, runner, event queues, and stub nodes.
- Structured run logging, secret redaction, and Prometheus metric definitions.
- Stage 12 React frontend pages, API client/hooks, UI tests, and Playwright smoke tests.
- Multi-stage non-root backend image, Nginx SPA frontend image, Compose health checks/migrations/sample seeding, and a hot-reload Compose override.
- CI for backend coverage/Ruff/mypy, frontend lint/type-check/tests/build, mock evals, and image builds; GHCR release workflow and repository templates.
- Mermaid system architecture source and generated 2x PNG.
- Stage 13 mock-provider evaluation harness, tool-boundary fault injection, input-size limits, and security-focused unit tests.

## Not implemented or incomplete

- Stage 7 planner/executor/retry/fallback logic: nodes remain stubs and do not make tool calls.
- Stage 8 evidence analysis, deterministic validation, report persistence/render pipeline, and source-conflict warnings.
- Versioned Stage 10 `/api/v1` routes. Current mounted routes are only `/health` and `/metrics`.
- Frontend-to-backend lifecycle integration; frontend expects `/api/v1` routes that are absent.
- Full Stage 13 agent-level chaos/security evaluation remains limited by the stubbed executor and missing upload API; coverage threshold and mock-layer benchmarks are implemented.
- The containerized UI can load and check `/health`; the Stage 10 `/api/v1` endpoints and real run execution remain unavailable.

## Roadmap order

Complete executable planning and reliable tool-loop behavior, then analysis/validation/report persistence, then the versioned API and UI integration. Follow with quality/evaluation gates and containerization. Keep the mock provider path deterministic and network-free throughout.
