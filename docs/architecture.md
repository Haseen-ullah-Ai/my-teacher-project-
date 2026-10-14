# Architecture

ResearchPilot is designed as a local, controlled research system. The diagrams distinguish the current scaffold from behavior that is specified but not implemented yet. In particular, the graph topology exists, but its nodes are stubs and the planned `/api/v1` lifecycle API is not mounted.

## System context and containers

```mermaid
flowchart LR
    User[User]
    UI[React 18 + TypeScript UI<br/>Vite]
    API[FastAPI application<br/>health + metrics]
    Runtime[LangGraph runner<br/>current nodes are stubs]
    Tools[Controlled local tool registry]
    DB[(PostgreSQL 16<br/>runs, logs, evidence, FTS)]
    LLM[LLM provider adapter<br/>mock by default]
    Files[(Configured local data<br/>documents, CSV, reports)]

    User --> UI
    UI -->|HTTP; planned /api/v1 not mounted| API
    API -. planned run lifecycle .-> Runtime
    Runtime --> Tools
    Runtime --> LLM
    Tools --> DB
    Tools --> Files
    Runtime --> DB
    LLM -. remote only when configured .-> OpenAI[OpenAI]
    LLM -. remote only when configured .-> Anthropic[Anthropic]
    LLM -. local service when configured .-> Ollama[Ollama]
```

The system diagram source is [`diagrams/system.mmd`](diagrams/system.mmd); `make diagrams` exports [`images/architecture.png`](images/architecture.png) at 2x scale. It requires Node/npm and downloads the pinned Mermaid CLI on first run. Windows without GNU Make can run the target command directly from the repository root:

```powershell
npx --yes @mermaid-js/mermaid-cli@11.4.2 -i docs/diagrams/system.mmd -o docs/images/architecture.png -b transparent -s 2
```

## Agent graph

The topology below matches [`agent_graph.mmd`](agent_graph.mmd). Intake, planning, tool execution, analysis, validation, persistence of tool attempts, and report generation are currently scaffold/stub behavior, not a functioning research workflow.

```mermaid
flowchart TD
    START([START]) --> intake[intake]
    intake --> planner[planner]
    planner --> select_tool[select_tool]
    select_tool -->|step remains| execute_tool[execute_tool]
    select_tool -->|no steps| analyzer[analyzer]
    select_tool -->|abort requested| END([END])
    execute_tool -->|success| collect[collect]
    execute_tool -->|failure| retry_or_fallback[retry_or_fallback]
    retry_or_fallback -->|retry| execute_tool
    retry_or_fallback -->|skip| collect
    retry_or_fallback -->|abort| END
    collect -->|more steps| select_tool
    collect -->|finished| analyzer
    collect -->|abort requested| END
    analyzer --> validator[validator]
    validator -->|passed| reporter[reporter]
    validator -->|failed; replan budget remains| planner
    validator -->|failed; budget exhausted| reporter
    reporter --> END
```

The route functions are deterministic state routers. Current code does not yet implement the planned dynamic plan creation, dependency resolution, retries/fallbacks, or validation/replanning behavior in the nodes.

## Run sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as React UI
    participant API as FastAPI
    participant Runner as AgentRunner
    participant Planner as Planner node
    participant Executor as Executor nodes
    participant Tools as Local tools
    participant Analyzer as Analyzer node
    participant Validator as Validator node
    participant Reporter as Reporter node
    participant DB as PostgreSQL

    User->>UI: Submit research task
    UI->>API: POST planned /api/v1/runs
    Note over UI,API: This route is not implemented/mounted yet.
    API->>Runner: Planned background-run handoff
    Runner->>DB: Create research_run
    Runner->>Planner: Invoke graph
    Planner-->>Runner: Stub status update
    Runner->>Executor: Select/execute/collect (stub)
    Executor->>Tools: Intended tool invocation
    Tools-->>Executor: Typed result (tools are independently implemented)
    Executor->>DB: Intended tool-call/evidence persistence
    Runner->>Analyzer: Invoke graph
    Analyzer->>Validator: Stub analysis
    Validator->>Reporter: Stub validation result
    Reporter->>DB: Intended report persistence
    Runner-->>UI: Intended SSE transitions
    Note over API,UI: SSE endpoint is not implemented/mounted yet.
```

## Persistence ER diagram

The entity names and primary relationships reflect SQLAlchemy models and migrations. A solid relationship indicates a foreign key in the current model. The report/run relationship includes a final-report pointer and a report-to-run foreign key.

```mermaid
erDiagram
    RESEARCH_RUNS ||--o{ PLAN_STEPS : plans
    RESEARCH_RUNS ||--o{ TOOL_CALLS : records
    PLAN_STEPS ||--o{ TOOL_CALLS : attempts
    RESEARCH_RUNS ||--o{ EXECUTION_LOGS : logs
    PLAN_STEPS o|--o{ EXECUTION_LOGS : annotates
    RESEARCH_RUNS ||--o{ FINDINGS : produces
    RESEARCH_RUNS ||--o{ VALIDATION_RESULTS : validates
    RESEARCH_RUNS ||--o{ REPORTS : has
    RESEARCH_RUNS o|--o| REPORTS : final_report
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : chunks

    RESEARCH_RUNS {
        uuid id PK
        text task
        string status
        jsonb plan
        uuid final_report_id FK
        text error
        int replan_count
        timestamptz created_at
        timestamptz started_at
        timestamptz finished_at
        bigint total_duration_ms
        int tool_call_count
        int retry_count
        int failure_count
        bigint token_count
        string llm_provider
    }
    PLAN_STEPS {
        uuid id PK
        uuid run_id FK
        int step_index
        text description
        string tool_name
        jsonb tool_args
        string status
        int retries
        int_array depends_on
    }
    TOOL_CALLS {
        uuid id PK
        uuid run_id FK
        uuid step_id FK
        string tool_name
        jsonb input
        jsonb output
        string status
        string error_type
        text error_message
        int attempt
        timestamptz started_at
        bigint duration_ms
    }
    EXECUTION_LOGS {
        bigint id PK
        uuid run_id FK
        uuid step_id FK
        string node
        string level
        string event
        text message
        jsonb data
        timestamptz created_at
    }
    FINDINGS {
        uuid id PK
        uuid run_id FK
        text statement
        jsonb evidence
        float confidence
        uuid_array source_tool_call_ids
    }
    VALIDATION_RESULTS {
        uuid id PK
        uuid run_id FK
        int attempt
        boolean passed
        jsonb checks
        timestamptz created_at
    }
    REPORTS {
        uuid id PK
        uuid run_id FK
        string title
        text summary
        jsonb content_json
        text content_markdown
        jsonb file_paths
        timestamptz created_at
    }
    DOCUMENTS {
        uuid id PK
        string filename
        string title
        string checksum UK
        string content_type
        bigint size_bytes
        timestamptz created_at
    }
    DOCUMENT_CHUNKS {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text content
        tsvector tsv
        jsonb metadata
    }
    DATASETS {
        uuid id PK
        string filename
        string checksum UK
        bigint row_count
        jsonb columns
        timestamptz created_at
    }
```

Document chunks have a generated PostgreSQL `tsvector` and GIN index. Dataset files themselves remain under the configured data directory; the `datasets` table records checksum and schema metadata.

## Retry and failure decision flow

```mermaid
flowchart TD
    Call[Execute registered tool] --> Outcome{ToolResult ok?}
    Outcome -->|yes| Collect[Collect result and provenance]
    Outcome -->|no| Type{Typed failure}
    Type -->|invalid input| Repair[Planned: one model-assisted argument repair]
    Type -->|timeout / transient execution| Count{Retries remain?}
    Count -->|yes| Backoff[Planned: exponential backoff + jitter]
    Backoff --> Call
    Count -->|no| Critical{Step critical?}
    Type -->|empty search / missing column| Fallback[Planned: broaden query / describe columns]
    Repair -->|repaired| Call
    Repair -->|still invalid| Critical
    Fallback --> Call
    Type -->|other| Critical
    Critical -->|non-critical| Skip[Planned: mark skipped and record limitation]
    Critical -->|critical| Abort[Planned: fail run with reason]
    Collect --> Circuit{More than 5 total failures?}
    Skip --> Circuit
    Circuit -->|yes| Abort
    Circuit -->|no| Next[Continue graph]
```

The flowchart is the intended reliability policy from the product specification. The current graph has retry/skip/abort routing edges, but the retry/fallback node is a stub and does not implement this policy.

## Operational boundaries

- No external web-search tool exists; tools are explicitly registered local operations.
- Document search and CSV access require PostgreSQL and registered/ingested records.
- `GET /health` and `GET /metrics` are mounted. The API lifecycle and SSE routes shown in design diagrams are planned only.
- PostgreSQL integration tests require a disposable isolated database. The fixture may drop/recreate tables.
