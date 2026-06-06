# P0-6 Governance Denied Column and Metadata Snapshot Replay

Status: implemented

Date: 2026-06-06

## Goal

Extend the active governance parity lane beyond binding forwarding into the
first queryModel-visible contracts that Java and Python can validate without
production code changes or Odoo business models.

This work item covers:

- `deniedColumns` physical-column to QM-field resolution.
- Query validation refusal for denied fields referenced by `columns`.
- Query validation refusal for denied fields referenced by `orderBy`.
- Pass-through for denied physical columns that do not map to the current QM.
- Metadata trimming with `deniedColumns`.
- Metadata trimming with `visibleFields` intersected by `deniedColumns`.

## Scope

In scope:

- Java snapshot producer extension:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/security/JavaGovernanceSnapshotTest.java`
- Python fixture extension:
  `tests/fixtures/java_governance_snapshot_parity.json`
- Python replay extension:
  `tests/integration/test_java_governance_snapshot_parity.py`
- Manifest lane update:
  `tests/fixtures/java_snapshot_parity_manifest.json`

Out of scope for this slice:

- Odoo model/domain fixtures.
- Visible model allow/deny lists from a real authority resolver.
- Cross-model calculated-field reference refusals.
- Sanitized error payload snapshots.
- Pivot/domain transport governance propagation.
- QueryModel aggregate join governance propagation.

## Contract Notes

The Java producer uses a neutral in-test `PhysicalColumnMapping` and invokes
`FieldAccessPermissionStep` directly. This avoids Spring, DB, and Odoo fixtures
while still exercising Java's runtime denied-column validation surface.

The Python replay uses the demo `FactSalesModel` registered in
`SemanticQueryService`, so it validates the real Python mapping cache,
`SemanticQueryRequest.deniedColumns`, query validation path, and
`get_metadata_v3` trimming behavior.

The shared cases use fields that are projectable in both runtimes. In
particular, the query-validation fixtures use `product$caption` as the neutral
non-denied dimension projection because Python's ecommerce model treats
dimension roots as non-projectable unless `$caption` or `$id` is specified.

## Acceptance

- Java producer passes with:
  `mvn test -pl foggy-dataset-model -Dtest=JavaGovernanceSnapshotTest`
- Python replay and manifest pass with:
  `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Ruff passes for the updated replay file.
- Full Python pytest baseline passes.
