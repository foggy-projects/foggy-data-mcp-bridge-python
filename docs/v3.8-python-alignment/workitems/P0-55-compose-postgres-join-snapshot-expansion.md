# P0-55 Compose PostgreSQL Join Snapshot Expansion

## Requirement

Close the PostgreSQL join success cell surfaced by the P0-52 compose snapshot
coverage inventory.

The snapshot must stay engine-neutral and compiler-level: no live database, no
registry pull, and no product-layer behavior.

## Scope

- Add a PostgreSQL `JoinPlan` success snapshot to `JavaComposeSnapshotTest`.
- Require strict SQL-shape replay for the new case.
- Regenerate `java_compose_snapshot_parity.json`.
- Update the Python coverage inventory test so `postgres/join` is no longer a
  missing success cell.

## Non-Goals

- Do not change compose compiler behavior unless the exporter reveals drift.
- Do not bundle SQLite compose enablement into this step.
- Do not add business-domain model assumptions.

## Acceptance

- Java exporter passes and writes the new snapshot.
- Python compose snapshot replay passes.
- Coverage inventory includes a PostgreSQL join success cell with strict SQL
  shape.
- `postgres/join` is absent from `missingSuccessCells`.
