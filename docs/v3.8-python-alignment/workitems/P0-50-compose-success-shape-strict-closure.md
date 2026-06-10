# P0-50 Compose Success Shape Strict Closure

## Requirement

Close the remaining non-strict SQL-shape checks in the compose snapshot lane.

After P0-49, all known Java/Python root-wrapper drift in successful compose
snapshots has been resolved. The remaining successful non-strict cases should
be promoted to `strictSqlShape=true` so future drift in root CTE/subquery shape
fails replay immediately.

## Scope

- Promote the remaining successful non-strict compose snapshot cases:
  - `derived-filter-order-limit-mysql8`
  - `union-all-sales-orders-mysql8`
  - `qualified-source-alias-slice-order-sqlserver`
- Keep error cases marker/error-only.
- Keep marker and param expectations unchanged.

## Non-Goals

- Do not add byte-for-byte SQL assertions.
- Do not add new compose scenarios.
- Do not change Python compile behavior.

## Acceptance

- Every successful case in `java_compose_snapshot_parity.json` has
  `expected.strictSqlShape=true`.
- Python compose snapshot replay and manifest stay green.
- Java exporter stays green.
