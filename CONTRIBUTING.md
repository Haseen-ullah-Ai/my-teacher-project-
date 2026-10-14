# Contributing to ResearchPilot

Thanks for helping improve ResearchPilot. Keep changes scoped, testable, and consistent with the controlled-data design.

## Before changing code

1. Check [current limitations](docs/limitations.md) so planned behavior is not mistaken for implemented behavior.
2. Identify the relevant project stage and avoid bundling unrelated future-stage work.
3. For tools, preserve explicit schemas, bounded execution, local-only access, and typed errors.
4. For evidence/report behavior, never invent citations or factual output.

## Development setup

Use Python 3.11+, Node.js 18+, npm, PostgreSQL 16, and a compatible `make` if using root targets. Follow the local setup in [README](README.md#quick-start-local-development). Start with the mock provider; it requires no model credentials.

## Checks

Run focused tests first, then relevant project checks:

```bash
make test
make lint
```

From `frontend/`:

```bash
npm test
npm run build
```

Browser tests require Playwright Chromium installation. PostgreSQL tests must use a disposable isolated database; the integration fixture drops and recreates tables.

## Pull requests

- Keep a PR focused and describe user-visible and operational effects.
- Add or update tests for behavior changes.
- Update relevant documentation and clearly label any remaining limitations.
- Do not commit `.env`, API keys, database dumps, generated private data, or local build output.
- Include commands run and their outcomes in the PR description.

## Style

Follow existing formatting and typing conventions. Backend checks use Ruff and mypy configuration in `backend/pyproject.toml`; frontend checks use the configured npm scripts. Prefer explicit errors over success-shaped fallback values.

