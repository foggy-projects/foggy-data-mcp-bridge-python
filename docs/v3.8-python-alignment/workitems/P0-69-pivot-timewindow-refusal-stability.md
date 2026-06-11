# P0-69 Pivot TimeWindow Refusal Stability

## Document Purpose

- doc_type: workitem
- intended_for: execution-agent, reviewer
- purpose: Track the Python fail-closed evidence for the Java-aligned `pivot + timeWindow` unsupported boundary.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete
Owner: Python engine alignment

## Background

Java treats direct `pivot + timeWindow` as an unsupported construct: time
intelligence should be expressed outside direct Pivot execution, and Pivot
keeps its own shaped result contract. The neutral domain/question runner
already exports a `pivot-time-window-mutual-exclusion-unsupported` case with
`unsupportedConstructs=["pivot+timeWindow"]`.

Python already had a runtime flat Pivot test for this boundary, but the
alignment evidence was thin: it did not prove the boundary across validate,
execute, governance query building, and Java fixture replay through the real
Python service.

## Scope

- Preserve the existing production fail-closed behavior in
  `validate_and_translate_pivot`.
- Add no-DB contract tests showing `pivot + timeWindow` is rejected in both
  validate and execute modes before timeWindow field validation.
- Add governance build-path coverage for the same boundary.
- Replay the Java neutral runner unsupported-case payload through the real
  Python `SemanticQueryService` and assert the stable fail-closed marker.
- Keep the unsupported-domain runner metadata and collector envelope unchanged.

## Out of Scope

- Enabling direct Pivot timeWindow execution.
- Rewriting domain/question neutral runner expected payloads.
- Java snapshot/export changes.
- Pivot cascade/tree/domain transport feature expansion.
- Odoo business model or generated model refresh.

## Acceptance Criteria

- `pivot + timeWindow` returns
  `PIVOT_FEATURE_NOT_IMPLEMENTED_IN_PYTHON: pivot + timeWindow is not supported`
  in validate and execute modes.
- Invalid `timeWindow.field` values do not leak into `TIMEWINDOW_FIELD_NOT_FOUND`
  when Pivot is present; the mutual-exclusion boundary wins first.
- `build_query_with_governance` raises the same fail-closed marker.
- The Java neutral fixture case
  `pivot-time-window-mutual-exclusion-unsupported` fails closed through the
  real Python service.
- Focused pytest and ruff checks pass.

## Constraints

- Do not touch Java or registry dirty work.
- Do not stage unrelated Python `charts/`.
- Keep this as evidence hardening only; do not change production compiler
  semantics unless a test proves drift.

## Expected Follow-Up

The next low-risk alignment item should move away from timeWindow unless a
stable Java live-result snapshot becomes available. Good candidates are a
bounded domain transport dialect/refusal edge case, or a focused aggregate-join
design-to-test bridge if Java 9.2 aggregate-join fixtures are ready.
