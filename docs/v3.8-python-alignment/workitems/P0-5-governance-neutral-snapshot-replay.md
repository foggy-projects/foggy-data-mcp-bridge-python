# P0-5 Governance Neutral Snapshot Replay

Status: implemented

Date: 2026-06-06

## Goal

Activate the first Java-to-Python parity lane for governance contracts without
touching production engine code or Odoo business models.

This work item covers a narrow, stable contract:

- `ModelBinding.fieldAccess` null vs empty-list semantics.
- Per-base forwarding of `fieldAccess`, `deniedColumns`, and `systemSlice`
  from Compose binding into the v1.3 semantic query boundary.
- Missing visible-model binding fail-closed compile error code and phase.

## Scope

In scope:

- Java snapshot producer:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/security/JavaGovernanceSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_governance_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_governance_snapshot_parity.py`
- Manifest lane activation in:
  `tests/fixtures/java_snapshot_parity_manifest.json`

Out of scope for this slice:

- Odoo model/domain fixtures.
- QueryModel metadata trimming snapshots.
- Full denied physical column SQL refusal snapshots.
- Cross-model calculated field denial snapshots.
- Sanitized error payload snapshots.

## Notes

The first slice intentionally validates the compiler boundary rather than
business-model behavior. Java captures the `SemanticRequestContext` received by
`SemanticQueryServiceV3.generateSql`; Python captures the
`SemanticQueryRequest` received by `SemanticQueryService.build_query_with_governance`.
Those are the corresponding v1.3 governance injection boundaries on each side.

The missing-binding case uses a hand-supplied empty bindings map to verify the
compiler's fail-closed surface: `compose-compile-error/missing-binding` at
phase `plan-lower`.

## Acceptance

- Java producer passes with:
  `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`
- Python replay passes with:
  `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py -q`
- Manifest gate includes the active `permission-visible-model-snapshots` lane.
