# P0-57 Compose SQL Server Union Snapshot Expansion

## Requirement

Close the SQL Server union success cell surfaced by the P0-52 compose snapshot
coverage inventory.

The snapshot must verify the SQL Server compose fallback remains free of
embedded `FROM (WITH` output.

## Scope

- Add a SQL Server `UnionPlan` success snapshot to `JavaComposeSnapshotTest`.
- Require strict SQL-shape replay for the new case.
- Regenerate `java_compose_snapshot_parity.json`.
- Update the Python coverage inventory test so `sqlserver/union` is no longer a
  missing success cell.

## Non-Goals

- Do not change lower-level dialect metadata; this is compose-level SQL-shape
  evidence.
- Do not add live SQL Server execution.
- Do not widen the lane into aggregate-join or product behavior.

## Acceptance

- Java exporter passes and writes the new snapshot.
- Python compose snapshot replay passes.
- Coverage inventory includes a SQL Server union success cell with strict SQL
  shape.
- `sqlserver/union` is absent from `missingSuccessCells`.
