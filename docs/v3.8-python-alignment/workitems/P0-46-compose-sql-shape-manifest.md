# P0-46 Compose SQL Shape Manifest

## Requirement

Promote compose snapshot SQL structure checks from marker-only assertions to a
fixture-level SQL shape manifest.

The Java exporter should publish a compact `expected.sqlShape` envelope for
each successful compose snapshot case. Python replay should compare stable
shape keys for every case and compare root CTE/subquery wrapping only when the
case is explicitly marked strict.

## Scope

- Add Java-exported `sqlShape` metadata for compose snapshot cases.
- Add `strictSqlShape` for cases whose root wrapper contract is already
  frozen, including base cross-dialect CTE/subquery cases and SQL Server
  fallback cases.
- Compare stable SQL shape keys in Python replay for every exported successful
  case.
- Compare full shape, including `rootUsesCte` and `rootUsesSubquery`, only for
  strict cases.
- Keep known non-strict root-wrapper drift visible in the fixture without
  failing replay.

## Non-Goals

- Do not rewrite PostgreSQL derived-over-join root wrapping in this work item.
- Do not assert byte-for-byte SQL parity.
- Do not add live database execution.
- Do not broaden the QueryModel aggregate-join line.

## Acceptance

- Java `JavaComposeSnapshotTest` exports `expected.sqlShape` for successful
  cases.
- Strict fallback cases also export `expected.strictSqlShape`.
- Python replay fails on stable join/union/where/order/fallback-shape drift.
- Python replay still accepts known non-strict Java/Python root-wrapper
  differences.
- Compose replay and manifest remain green.
