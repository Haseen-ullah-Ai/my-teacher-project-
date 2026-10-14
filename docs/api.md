# API reference and current availability

## Mounted endpoints

The FastAPI application in `backend/app/main.py` currently registers only:

| Method | Path | Response | Notes |
|---|---|---|---|
| `GET` | `/health` | `{"status":"ok","version":"0.1.0","db":"ok"}` | `db` is `down` if a connectivity check fails. |
| `GET` | `/metrics` | Prometheus text | Excluded from generated OpenAPI schema. |

An `X-Request-ID` is accepted or generated and returned on responses. CORS origins are configured by `CORS_ORIGINS`.

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/metrics
```

OpenAPI/Swagger is served by FastAPI at `/docs`; it currently documents the mounted health operation. Metrics is hidden from OpenAPI.

## Source-only, unmounted legacy router

`backend/app/api/routes.py` contains a router with `GET /api/health` and `POST /api/tasks`. It is not included in `create_app()` and is therefore unavailable on the running server. Its `POST /api/tasks` response is an older `ResearchReport` skeleton, not the planned async run API.

## Planned Stage 10 API (not implemented)

The following is an inventory of the intended contract, not callable endpoints. The React client currently targets these `/api/v1` paths, but the backend does not mount them.

| Method | Planned path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Start run; return `202` and run id. |
| `GET` | `/api/v1/runs` | Paginated/filterable run list. |
| `GET` | `/api/v1/runs/{id}` | Run, plan, findings, validation, metrics. |
| `GET` | `/api/v1/runs/{id}/logs` | Incrementally query logs. |
| `GET` | `/api/v1/runs/{id}/tool-calls` | List all attempts. |
| `GET` | `/api/v1/runs/{id}/events` | SSE transition stream with replay cursor. |
| `POST` | `/api/v1/runs/{id}/cancel` | Cooperatively cancel a run. |
| `POST` | `/api/v1/runs/{id}/retry` | Create a run for the original task. |
| `GET` | `/api/v1/runs/{id}/report` | Structured report. |
| `GET` | `/api/v1/runs/{id}/report/download` | Download Markdown, PDF, or JSON. |
| `GET`, `POST`, `DELETE` | `/api/v1/documents[/{id}]` | List, ingest, and delete documents. |
| `GET`, `POST` | `/api/v1/datasets[/{id}]` | List, register, and preview CSV datasets. |
| `GET` | `/api/v1/tools` | Registry metadata and schemas. |
| `GET` | `/api/v1/stats/overview` | Dashboard aggregates. |
| `GET` | `/api/v1/health`, `/api/v1/metrics` | Versioned health and metrics, if retained by implementation. |

The Stage 10 product contract also calls for uniform error envelopes, rate limiting, concurrent-run limiting, uploads, and SSE. These are not currently available as `/api/v1` behaviors.

## Frontend integration note

The Stage 12 UI has a typed API client and hooks for the planned endpoint contract. Its browser flows should be considered UI scaffolding until the backend API routes and actual graph execution are implemented. Use `/health` and `/metrics` to check the current backend.

