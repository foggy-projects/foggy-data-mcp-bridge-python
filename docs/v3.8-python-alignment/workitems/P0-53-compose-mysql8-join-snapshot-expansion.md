# P0-53 Compose MySQL8 Join Snapshot Expansion

## Requirement

Close the first concrete gap surfaced by the P0-52 compose snapshot coverage
inventory by adding a Java-exported MySQL8 join success case.

The case should remain neutral and compiler-level: no live database, no
business model registry, and no product-layer behavior.

## Scope

- Add a `mysql8` `JoinPlan` success snapshot to
  `JavaComposeSnapshotTest`.
- Require strict SQL-shape replay for the new case.
- Regenerate `java_compose_snapshot_parity.json`.
- Update the Python coverage inventory test so `mysql8/join` is no longer
  treated as a missing success cell.
- Keep remaining missing cells visible for future targeted expansion.

## Non-Goals

- Do not add broad dialect-matrix cases in one batch.
- Do not change compose compiler behavior unless the snapshot reveals drift.
- Do not introduce SQLite compose coverage in this step.

## Acceptance

- Java exporter passes and writes the new snapshot.
- Python compose snapshot replay passes.
- Coverage inventory reports `17/17` strict successful compose snapshots.
- `mysql8/join` is absent from `missingSuccessCells`.
