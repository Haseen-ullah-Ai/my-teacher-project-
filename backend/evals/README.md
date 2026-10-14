# Mock-provider evaluations

Run the deterministic 10-task benchmark suite from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m evals.run
```

macOS/Linux:

```bash
.venv/bin/python -m evals.run
```

The harness exercises the mock planner and analyzer directly without PostgreSQL, model credentials, or network access. It validates expected tool selection, finding keywords, evidence references, and whether supplied synthetic source-conflict metadata appears as a limitation. Tool outputs are explicit synthetic fixtures; these scores are **not** end-to-end agent or business-research quality measurements while the LangGraph nodes remain stubs.

Each YAML benchmark specifies `task`, `expected_tools`, `expected_findings_keywords`, `must_cite`, and `should_flag_conflict`. Summary rows include task id, pass state, planned tools, retries (zero for direct mock calls), validation status, and elapsed duration. Full results are written to `evals/results/latest.json`.
