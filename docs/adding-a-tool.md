# Adding a controlled tool

This guide adds a local tool to the explicit registry. Tools are the only intended way for an agent workflow to touch user data.

## 1. Define strict Pydantic schemas

Add input/output models in `backend/app/tools/schemas.py` (or a narrowly scoped schema module if the project later splits them). Inherit the tool input model from `StrictModel` so unknown fields are rejected. Add field constraints and operation-specific validation where necessary.

```python
from pydantic import Field

from app.tools.schemas import StrictModel


class ExampleInput(StrictModel):
    query: str = Field(min_length=1, max_length=300)


class ExampleOutput(StrictModel):
    matches: list[str]
```

Do not include filesystem paths, SQL fragments, or executable source in the planner-controlled input unless there is a specific validated design for them.

## 2. Implement `BaseTool`

Create a module under `backend/app/tools/`. Give the tool a stable registry name, user-facing purpose, schema classes, and a bounded timeout. Implement only the operation described by the schema.

```python
from app.tools.base import BaseTool


class ExampleTool(BaseTool[ExampleInput, ExampleOutput]):
    name = "example"
    description = "Searches the approved local example catalog."
    input_model = ExampleInput
    output_model = ExampleOutput
    timeout = 10.0

    async def run(self, input: ExampleInput) -> ExampleOutput:
        """Search only the configured local catalog."""
        return ExampleOutput(matches=[])
```

The sample return above is only a shape illustration; production code must implement the actual operation and must not silently return success-shaped empty data when something failed. Raise a typed error from `app/core/errors.py` when appropriate. `BaseTool.execute()` validates input/output, enforces timeout, and wraps failures.

## 3. Register it

Add the import and one `registry.register(...)` call in `build_default_registry()` in `backend/app/tools/registry.py`. Duplicate names are rejected. Registry descriptions are generated from the tool's Pydantic schemas.

## 4. Enforce resource boundaries

- Resolve configured paths and verify the resolved target remains under the allowed root.
- Require database records/registration where the existing data model requires it.
- Bound input sizes, result sizes, and execution time.
- Never add arbitrary code execution or public web browsing.
- Treat retrieved document text as data, not as instructions.
- Do not log credentials or unnecessarily sensitive payloads.

## 5. Add focused tests

Add unit tests under `backend/tests/unit/` covering:

- valid input and output;
- missing and extra fields;
- operation-specific invalid combinations;
- typed runtime errors and timeout behavior;
- path traversal / unauthorized resource access when relevant;
- bounded result sizes and stable provenance.

Use fake repositories/sessions for isolated tool tests. PostgreSQL-dependent integration tests must use a dedicated disposable database named to include `test`; the fixture drops and recreates tables.

## 6. Verify

From the repository root:

```bash
make test
make lint
```

Or from `backend/` with the project venv:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests
```

macOS/Linux:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
```

The current graph executor does not yet invoke registered tools as part of full runs. Registry inclusion makes the tool available to the dependency container; wiring a live executor belongs to the agent-execution stage, not just tool registration.
