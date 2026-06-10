# P0-49 Compose Derived Composed Root Wrapper Parity

## Requirement

Close the root-wrapper drift exposed by P0-46 for `DerivedQueryPlan` over a
composed source (`JoinPlan` or `UnionPlan`).

Java treats a derived query whose source compiles to `ComposedSql` as terminal
SQL: the derived `SELECT ... FROM (<join-or-union-sql>) AS cte_N` is returned
directly and is not wrapped again as a top-level `WITH cte AS (...) SELECT *`.
Python should follow the same compile contract so strict SQL-shape replay can
cover these cases.

## Scope

- Mirror Java `compileDerived` behavior in Python:
  - if the derived source compiles to `ComposedSql`, wrap it only as a local
    inner unit for outer-select rendering;
  - return the rendered outer SQL as terminal `ComposedSql`;
  - skip `CteUnit` dedup caching for that terminal derived result.
- Promote existing Java compose snapshot cases to strict SQL-shape replay:
  - `qualified-source-alias-join-postgres`
  - `qualified-source-alias-slice-order-postgres`
  - `qualified-source-alias-slice-order-mysql8`
  - `inherited-source-alias-through-derived-postgres`
  - `union-result-alias-qualified-ref-postgres`
  - `stable-reused-base-qualified-ref-postgres`
- Keep marker checks and params unchanged.

## Non-Goals

- Do not add byte-for-byte SQL golden assertions.
- Do not change SQL Server fallback semantics.
- Do not broaden QueryModel aggregate-join support.
- Do not touch domain/question neutral-runner fixture work.

## Acceptance

- Python root-wrapper shape matches Java for all current successful compose
  snapshots.
- The six formerly non-strict derived-over-composed snapshot cases now replay
  with `strictSqlShape=true`.
- Java exporter and Python replay remain green.
