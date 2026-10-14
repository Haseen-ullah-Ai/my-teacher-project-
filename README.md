<div align="center">

# ResearchPilot

### Controlled, evidence-first research over your local business data

[![CI](https://img.shields.io/badge/CI-basic%20workflow-yellow)](.github/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-not%20measured-lightgrey)](docs/limitations.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&logoColor=white)](frontend/package.json)

</div>

ResearchPilot is a portfolio project for running auditable research against an organization's own documents and CSVs. It combines a typed React interface with a FastAPI/LangGraph backend, PostgreSQL persistence and full-text search, and a small registry of controlled local tools. A deterministic mock LLM is the default, so the provider layer can be exercised without API credentials.

> **Implementation status:** the repository contains the scaffold, persistence layer, sample-data ingestion, controlled tool implementations, LLM provider adapters, graph topology, execution logging/metrics, a basic CI workflow, a development Docker Compose stack, and Stage 12 UI. The agent graph's planner/executor/analyzer/validator/reporter nodes are still scaffolds, and the `/api/v1` API consumed by the UI has not yet been implemented. The UI is therefore not yet connected to a live end-to-end research workflow. See [limitations and roadmap](docs/limitations.md).

## Screenshots and diagrams

Screenshots/GIFs are intentionally left as capture placeholders until the API-backed UI is available. The system architecture diagram is generated from Mermaid source:

![ResearchPilot system architecture](docs/images/architecture.png)

Planned capture locations:

- `docs/images/dashboard.png`
- `docs/images/run-detail.png`
- `docs/images/research-flow.gif`

## Key features in the current repository

- **Offline-capable model layer:** deterministic mock provider, with optional OpenAI, Anthropic, and Ollama adapters.
- **Explicit local tool registry:** document search, registered-CSV analysis, restricted AST calculator, and Markdown/PDF report renderer.
- **Evidence-ready persistence model:** runs, plans, attempts, execution logs, findings, validations, reports, indexed document chunks, and dataset metadata.
- **PostgreSQL full-text search:** generated `tsvector` column and GIN index; no external vector database.
- **Path-bounded data access:** CSV reads are constrained to the configured data directory and registered datasets.
- **Execution observability:** structured run logs, secret-field redaction, run counters, Prometheus metrics, and request correlation IDs.
- **Research workspace UI:** responsive pages for overview, new research, runs, run detail, document/dataset management, tools, and settings.
- **Repeatable sample data:** deterministic, seeded CSV generation and checksum-based ingestion idempotency.

## Technology

| Area | Technology |
|---|---|
| Backend API | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| Agent orchestration | LangGraph |
| Persistence | PostgreSQL 16, SQLAlchemy 2 async, asyncpg, Alembic |
| Local tools | pandas, NumPy, Python AST, ReportLab |
| LLM adapters | httpx; mock, OpenAI, Anthropic, Ollama |
| Logging and metrics | structlog, Prometheus client |
| Frontend | React 18, TypeScript strict mode, Vite, Tailwind CSS |
| Frontend state/routing/charts | TanStack Query, React Router, Recharts, Lucide |
| Tests | pytest, pytest-asyncio, Vitest, React Testing Library, Playwright |

## Architecture

The intended request path is:

```text
User -> React UI -> FastAPI -> LangGraph runtime
                              -> registered local tools
                              -> PostgreSQL (runs, logs, evidence, documents)
                              -> optional configured LLM provider
```

The designed graph is `intake -> planner -> tool-selection/execution/collection loop -> analyzer -> validator -> reporter`. The current graph has this topology, but its nodes are stubs; it does not yet conduct factual research. See [architecture and Mermaid diagrams](docs/architecture.md), [tools](docs/tools.md), and the generated [graph source](docs/agent_graph.mmd).

## Quick start: Docker development stack

Docker Compose builds a slim, non-root backend image and an Nginx frontend image, starts PostgreSQL, waits for its health check, then runs migrations and idempotent sample-data ingestion from the backend entrypoint. The local stack has seeded data, but the agent nodes and `/api/v1` research lifecycle remain incomplete.

Prerequisite: Docker Engine with the Compose plugin.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build
```

In a second terminal, check the API:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Then open <http://localhost:3000>. On macOS/Linux, use `cp -n .env.example .env` and `curl http://localhost:8000/health`. Nginx proxies `/api/` (with buffering disabled for SSE) and `/health` to the backend. The mock provider is used by default and no API key is needed. Stop with `docker compose down`; omit `-v` to retain PostgreSQL data, sample files, and reports.

For hot reload on both services, use `make dev-stack` (or `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`); the Vite frontend is available at <http://localhost:5173>.

## Quick start: local development

For a non-container setup, use a reachable PostgreSQL 16 instance. Use separate terminals after installing prerequisites.

1. Copy the example configuration and set a PostgreSQL URL:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   # Edit DATABASE_URL in .env for your local PostgreSQL instance.
   ```

   macOS/Linux:

   ```bash
   cp -n .env.example .env
   # Edit DATABASE_URL in .env for your local PostgreSQL instance.
   ```

2. Install the Python backend and apply migrations:

   ```powershell
   cd backend
   py -3 -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements-dev.txt
   .\.venv\Scripts\alembic upgrade head
   ```

   macOS/Linux (from the repository root):

   ```bash
   cd backend
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements-dev.txt
   .venv/bin/alembic upgrade head
   ```

3. In a backend terminal, start the API:

   ```powershell
   # From backend/
   .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
   ```

   macOS/Linux:

   ```bash
   # From backend/
   .venv/bin/python -m uvicorn app.main:app --reload --port 8000
   ```

4. In a second backend terminal, generate and ingest the sample files (database must be running and migrated):

   ```powershell
   # From the repository root:
   backend\.venv\Scripts\python.exe scripts\seed.py
   ```

   macOS/Linux:

   ```bash
   # From the repository root:
   backend/.venv/bin/python scripts/seed.py
   ```

5. In a frontend terminal:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

   Open <http://localhost:5173>. The frontend currently calls the planned `/api/v1` API, which is not implemented yet; its screens render but live data and run submission will show connection/API errors until that stage is complete.

Health and observability endpoints currently registered by the FastAPI application:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

Expected health response shape: `{"status":"ok","version":"0.1.0","db":"ok"}`. The `db` field reports whether PostgreSQL is reachable.

### Database and sample data

The database must be created by PostgreSQL before Alembic runs. The application does not create a database server or database automatically. After creating the venv and installing dependencies as above, run these commands from the repository root:

```powershell
backend\.venv\Scripts\alembic.exe upgrade head
backend\.venv\Scripts\python.exe scripts\generate_sample_data.py
backend\.venv\Scripts\python.exe scripts\seed.py
```

macOS/Linux:

```bash
backend/.venv/bin/alembic upgrade head
backend/.venv/bin/python scripts/generate_sample_data.py
backend/.venv/bin/python scripts/seed.py
```

The ingestion script stores document chunks and dataset metadata. It requires a reachable PostgreSQL database. Generated data files are under `data/`; documents are chunked with paragraph/sentence-aware boundaries and overlap. Checksums make repeat ingestion idempotent.

### Useful development commands

Run backend tests and lint from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests
```

macOS/Linux:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
```

GNU Make shortcuts (requires GNU Make, which is not included with standard Windows PowerShell):

```bash
make test
make lint
```

Run frontend checks from `frontend/`:

```bash
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The integration tests skip unless `TEST_DATABASE_URL` points to a dedicated disposable database whose name contains `test`. The fixture drops and recreates tables in that database: never set it to a development or production database.

## Configuration

Backend settings are loaded from environment variables and the repository-root `.env` file. The mock provider is the default. `VITE_API_BASE_URL` is a Vite build-time variable; set it before starting/building the frontend.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Application environment label. |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/researchpilot` | Async SQLAlchemy PostgreSQL URL. |
| `DATA_DIR` | `../data` | Root for local document and CSV data, resolved relative to the backend package. |
| `REPORTS_DIR` | `../reports` | Local directory for generated Markdown/PDF reports. |
| `LLM_PROVIDER` | `mock` | One of `mock`, `openai`, `anthropic`, or `ollama`. |
| `LLM_MODEL` | `mock-model` | Model name passed to the selected provider. |
| `LLM_API_KEY` | empty | Credential for providers that require a key. Keep it out of source control. |
| `LOG_LLM_PROMPTS` | `false` | When true, permits raw prompts in run logs; default logs prompt hashes instead. |
| `TOOL_TIMEOUT_SECONDS` | `30` | Configured default; individual tool classes currently set their own explicit timeouts. |
| `MAX_TOOL_RETRIES` | `3` | Configured maximum retry count. The agent retry node is not implemented yet. |
| `MAX_REPLANS` | `2` | Configured maximum replan count. The agent planner/replan node is not implemented yet. |
| `LOG_LEVEL` | `INFO` | Structured application logging level. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | JSON array of allowed frontend origins; Compose defaults to port 3000 for its Nginx-served UI. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL used by the browser client. |
| `TEST_DATABASE_URL` | unset | Test-only URL for a disposable PostgreSQL database. Not consumed by application settings. |
| `CI` | unset locally | Set by CI environments; Playwright uses it to decide whether to reuse a running Vite server. |
| `POSTGRES_DB` | `researchpilot` | Development Compose PostgreSQL database name. |
| `POSTGRES_USER` | `researchpilot` | Development Compose PostgreSQL user; local-only default. |
| `POSTGRES_PASSWORD` | `researchpilot_local_only` | Local Compose password from `.env.example`; replace for any shared deployment. |

## Selecting a real LLM provider

The default `LLM_PROVIDER=mock` makes no network calls and needs no API key. To configure a remote provider, set the provider and model and put its API key in an untracked `.env` file. For example:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=replace-with-your-own-key
```

Supported provider names are `openai`, `anthropic`, and `ollama`; check each provider's own model naming and local service requirements. Do not commit real credentials. The currently scaffolded graph does not call the LLM nodes; switching providers can be verified through the provider layer, but does not yet turn a run into real research.

## Usage walkthrough

1. Generate/ingest the sample documents and CSVs with the database available.
2. Start the API and frontend as shown above.
3. Use the dashboard and New Research page to explore the UI; live submissions are awaiting the versioned API.
4. Independently exercise the controlled tools with the demo (requires PostgreSQL and seeded data for search/CSV calls):

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m app.tools.demo
   ```

   macOS/Linux:

   ```bash
   cd backend
   .venv/bin/python -m app.tools.demo
   ```

5. Use the calculator with expressions such as `pct_change(100, 112)` (returns `12`) or `pct_of(25, 200)` (returns `12.5`). The evaluator rejects Python names, attribute access, arbitrary calls, large expressions, and excessive exponents; it never uses `eval`.

Sample natural-language tasks for the eventual UI workflow:

- “Analyze Q3 sales by region, compare against targets, and recommend actions.”
- “Summarize customer satisfaction by region and identify risk thresholds.”
- “Compare supplier delivery dates and defect rates with the supplier review.”

At present these are examples, not verified end-to-end outputs. Stage 7/8 agent behavior is still stubbed; see [sample run](docs/sample-run.md).

## API overview

The running app currently exposes:

- `GET /health` — application version and database reachability.
- `GET /metrics` — Prometheus exposition.

There is a legacy `APIRouter` source file for `GET /api/health` and `POST /api/tasks`, but `create_app()` does not mount that router. These endpoints are **not** available over the current running app. The Stage 12 frontend expects the planned Stage 10 `/api/v1` contract, which also is **not implemented**. Refer to [API status and endpoint reference](docs/api.md) before integrating a client.

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── agent/       # LangGraph topology, state, stub nodes, runner
│   │   ├── api/         # Current unmounted legacy router and dependencies
│   │   ├── core/        # Settings, errors, structured logging
│   │   ├── db/          # Async SQLAlchemy base and sessions
│   │   ├── llm/         # Provider protocol, adapters, prompt templates
│   │   ├── models/      # Run, log, evidence, report, document, dataset tables
│   │   ├── repositories/# Database data access
│   │   ├── schemas/     # API/database Pydantic schemas
│   │   ├── services/    # Ingestion, metrics, run logging
│   │   └── tools/       # Four controlled local tools and registry
│   ├── alembic/         # Async migrations
│   ├── evals/           # Ten deterministic mock-provider benchmarks
│   └── tests/           # Unit and PostgreSQL integration tests
├── data/
│   ├── csv/             # Deterministic sample CSVs
│   └── documents/       # Northwind Retail Group sample policies/reports
├── docs/                # Architecture, tool, validation, API, and operations docs
├── frontend/
│   ├── e2e/             # Playwright browser smoke tests
│   └── src/             # React routes, API client, hooks, and components
├── scripts/             # Sample generation and database seed
├── .github/workflows/   # Backend, frontend, eval, Docker, and release CI
├── docker-compose.yml   # Health-checked stack with migration and seed entrypoint
├── docker-compose.dev.yml # Hot-reload development override
├── backend/Dockerfile
├── frontend/Dockerfile
├── .env.example
└── Makefile
```

## Design decisions and trade-offs

- **LangGraph:** makes the intended state machine, conditional routes, retries, and replan edges explicit. It is used for topology and stub execution now; end-to-end node behavior remains future work.
- **PostgreSQL full-text search:** `tsvector` + GIN provides local, SQL-native document retrieval without an external vector database. It is lexical rather than semantic search.
- **Deterministic mock LLM:** keeps demos and tests repeatable and credential-free; it is not a substitute for model-quality evaluation.
- **Controlled local tools:** data reads are intentionally narrow and explicit, with schema validation and path confinement. There is no browsing tool and no arbitrary code execution.
- **Async SQLAlchemy:** keeps database access nonblocking under FastAPI and supports explicit session injection into services.
- **Scope transparency:** design docs describe the intended architecture separately from incomplete runtime behavior.

## Tests, quality checks, and evaluations

Quality checks:

```powershell
# Backend (from backend/)
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\python.exe -m mypy app

# Frontend (from frontend/)
cd ..\frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Use `.venv/bin/python -m mypy app` for strict type checking on macOS/Linux, alongside `.venv/bin/python` and `.venv/bin/ruff`; run frontend commands from `frontend/`.

Pytest enforces an 85% backend coverage floor. Run `python -m evals.run` from `backend/` for the 10-task deterministic mock-provider evaluation suite; it writes `evals/results/latest.json`. CI runs Ruff, strict mypy, PostgreSQL-backed tests and a coverage artifact upload, frontend lint/type-check/tests/build, evaluations, and both Docker builds. PostgreSQL integration tests require a dedicated test database; unit, frontend component, and intercepted Playwright tests run without it.

The backend image installs the exact Linux/Python runtime pins in [`backend/requirements-lock.txt`](backend/requirements-lock.txt); local development uses the exact direct pins in `requirements.txt` and `requirements-dev.txt`, and the frontend uses `package-lock.json`. See the [Stage 16 release audit](docs/AUDIT.md) for current completion status and known release blockers.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), follow the stage/scope notes in [limitations](docs/limitations.md), and include focused tests for behavior changes. Security issues should follow [SECURITY.md](SECURITY.md).

## License

ResearchPilot is distributed under the [MIT License](LICENSE).
