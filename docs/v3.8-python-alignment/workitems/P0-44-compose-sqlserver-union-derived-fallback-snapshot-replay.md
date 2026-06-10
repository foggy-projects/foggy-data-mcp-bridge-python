# P0-44 Compose SQL Server Union Derived Fallback Snapshot Replay

## Requirement

Expand compose dialect SQL-shape coverage for SQL Server when a `UNION ALL`
plan is used as the source of a derived query.

The derived query must be able to use the union result alias for qualified
projection, slice, and orderBy refs while SQL Server output stays free of the
invalid embedded `FROM (WITH` shape.

The same lane also locks the root SQL Server derived-chain contract to Java's
subquery fallback shape, keeping top-level `WITH` out of this snapshot case.

## Scope

- Add a Java neutral compose snapshot case for SQL Server
  union-result-alias refs under a derived query.
- Replay the Java fixture in Python.
- Add focused Python coverage for the same SQL Server shape without depending
  only on fixture replay.
- Add focused Python coverage for root derived-chain subquery fallback.
- Preserve the existing union-as-source boundary: branch source aliases remain
  hidden after the union boundary.

## Non-Goals

- Do not change source-alias semantics.
- Do not reopen P0-37/P0-42/P0-43 signoff.
- Do not add live SQL Server execution requirements.

## Acceptance

- Java `JavaComposeSnapshotTest` exports
  `sqlserver-union-result-alias-derived-fallback`.
- Python replay validates the new fixture.
- Python local coverage verifies `UNION ALL`, `WHERE`, `ORDER BY`, params, and
  absence of `FROM (WITH`.
- Python local coverage verifies root derived-chain subquery fallback without
  top-level `WITH`.
- Focused Java/Python tests pass.
