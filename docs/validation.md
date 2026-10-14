# Validation

## Current behavior

The `validator` graph node is currently a topology-test stub. It reuses an existing state validation value or creates a passing empty `ValidationResult`, emits a `stub_validation` log event, and returns. It does **not** currently perform the deterministic checks or rubric-based LLM review specified below. No validation result is persisted by this node today.

The following catalog documents the intended validation policy for the completed research workflow; treat it as design, not as a claim that the checks run.

## Planned validation checks

| Check | Pass condition | Failure / warning behavior | Rationale |
|---|---|---|---|
| `plan_coverage` | Every non-skipped planned step has a successful tool call. | Fail deterministic validation if a required step lacks a successful attempt. | Prevents unsupported conclusions when the planned research did not execute. |
| `evidence_integrity` | Every cited evidence identifier resolves to a real tool call, document chunk, or supported CSV provenance record. | Fail if any citation is dangling. | A citation must be verifiable, not merely plausible-looking. |
| `citation_coverage` | Every finding cites at least one evidence reference. | Fail if a finding is uncited. | Enforces evidence-backed reporting. |
| `numeric_consistency` | Re-running each numeric derivation through the calculator agrees within 0.5%. | Fail if the recalculated value exceeds tolerance. | Detects arithmetic errors and unsupported numerical transformations. |
| `source_agreement` | Sources relevant to the same value are consistent. | Warning when sources disagree; report the conflict as a limitation. | Makes contradictory source data visible instead of silently choosing one. |
| `schema_validity` | Draft conforms to `ReportDraft`. | Fail schema validation on invalid structure/types. | Keeps generated artifacts consumable and predictable. |
| `scope_compliance` | Report respects explicitly out-of-scope constraints. | Fail if prohibited scope/content is introduced. | Keeps the agent inside the user's requested boundaries. |

The intended rubric-based LLM review assigns numeric scores to relevance, unsupported claims, and clarity. It is not a free-form approval. Planned replan routing fails when deterministic checks 1–4 fail or relevance is below 0.6, bounded by the configured `MAX_REPLANS`.

## Evidence model

The schema layer includes evidence reference models for reports and findings. The intended execution flow associates citations with stable source identifiers, such as tool-call UUIDs or document chunk UUIDs. CSV row-range citations are not yet implemented by the agent workflow; the CSV tool currently returns dataset-level provenance and filter metadata.

## Testing guidance

When these checks are implemented, test each check with both a valid and invalid fixture. Include a missing tool call, dangling evidence id, uncited finding, derivation mismatch above 0.5%, source conflict warning, invalid `ReportDraft`, and prohibited scope content. Test the graph's replan cap separately from individual check logic.

