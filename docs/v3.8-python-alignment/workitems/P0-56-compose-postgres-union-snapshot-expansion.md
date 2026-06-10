# P0-56 Compose PostgreSQL Union Snapshot Expansion

## Requirement

Close the PostgreSQL union success cell surfaced by the P0-52 compose snapshot
coverage inventory.

The snapshot should record the current Java compiler behavior for top-level
union output and replay that shape in Python.

## Scope

- Add a PostgreSQL `UnionPlan` success snapshot to `JavaComposeSnapshotTest`.
- Require strict SQL-shape replay for the new case.
- Regenerate `java_compose_snapshot_parity.json`.
- Update the Python coverage inventory test so `postgres/union` is no longer a
  missing success cell.

## Non-Goals

- Do not force PostgreSQL top-level union through CTE wrapping when Java emits a
  direct `SELECT ... UNION ALL ...` shape.
- Do not add live database execution.
- Do not introduce SQLite compose coverage in this step.

## Acceptance

- Java exporter passes and writes the new snapshot.
- Python compose snapshot replay passes.
- Coverage inventory includes a PostgreSQL union success cell with strict SQL
  shape.
- `postgres/union` is absent from `missingSuccessCells`.
