# Security policy

## Supported versions

ResearchPilot is currently an actively developed portfolio project. Security fixes are made on the current default branch; there are no formal release branches or service-level guarantees yet.

## Reporting a vulnerability

Please do not report exploitable vulnerabilities in a public issue. Use the repository host's private vulnerability reporting feature if enabled, or contact the maintainers through the private contact method listed in the repository profile. Include:

- a concise description and impact;
- affected version/commit and configuration;
- safe reproduction steps or a proof of concept that does not access third-party data;
- any suggested mitigation.

Do not include real credentials, private user data, or destructive payloads. The maintainers will acknowledge receipt, investigate, and coordinate a fix and disclosure timeline.

## Security boundaries

- Start from `.env.example`; keep `.env` and real credentials out of version control.
- Keep `LLM_PROVIDER=mock` for offline demos and tests.
- CSV access is intended to stay inside the configured data directory and requires dataset registration/checksum verification.
- Document search operates over locally ingested content; retrieved text is untrusted data, not executable instructions.
- The calculator uses an AST allowlist rather than `eval`.
- Run integration tests only against an isolated disposable PostgreSQL database; the fixture may drop and recreate tables.
- Do not expose the development server or database to untrusted networks.

The planned Stage 10 upload and rate-limit protections are not yet implemented as the `/api/v1` lifecycle API; do not treat the current scaffold as production-hardened for public deployment.

