# P0-37 Compose Source Alias Qualified Ref Snapshot Expansion

Date: 2026-06-09

## Goal

Refresh the compose alias/qualified-ref parity lane and define the next
engine-neutral fixture expansion before changing compile behavior.

## Current Coverage

The active Java compose snapshot fixture already covers:

- base query SQL markers,
- derived filter/order/limit SQL markers,
- union all,
- PostgreSQL qualified source-alias join projection,
- PostgreSQL source-alias refs in outer projection, slice, and orderBy after
  join,
- inherited source-alias refs through a derived query that retains projected
  fields before the next join,
- duplicated source alias prefixes across join sides fail closed as ambiguous,
- projected column aliases that shadow visible source aliases fail closed,
- dropped-column source alias refusal,
- union branch source aliases fail closed after the union boundary,
- union result aliases can qualify union output fields,
- MySQL8, PostgreSQL, and SQL Server qualified source-alias slice/order
  markers,
- SQL Server derived-chain fallback guard against `FROM (WITH`.

Python replay is anchored by:

- `tests/fixtures/java_compose_snapshot_parity.json`
- `tests/integration/test_java_compose_snapshot_parity.py`
- `tests/compose/compilation/test_join.py`

## Completed Expansion

Added Java snapshot cases:

- `qualified-source-alias-slice-order-postgres`
- `qualified-source-alias-slice-order-mysql8`
- `qualified-source-alias-slice-order-sqlserver`
- `inherited-source-alias-through-derived-postgres`
- `ambiguous-duplicate-source-alias-ref-refused`
- `source-alias-shadowed-by-projected-alias-refused`
- `union-branch-source-alias-ref-refused`
- `union-result-alias-qualified-ref-postgres`

The Python replay harness now reconstructs derived snapshot nodes through
`QueryPlan.query(...)` instead of direct `from_(source=...)` construction, so
replay uses the same compose alias propagation path as production callers.

Java and Python now both reject qualified refs such as `dup.salesAmount` when
the `dup` source alias is bound on both join sides. Callers must use
`left`/`right` or distinct source aliases.

Java and Python now reject derived projections such as `salesAmount AS sales`
when `sales` is a visible source alias, preventing later `sales.*` references
from becoming semantically unstable.

Union-as-source now keeps branch aliases hidden after the union boundary while
allowing a local union result alias such as `combined.amount`.

## Remaining Expansion

P0-37/P0-42 source-alias boundary work is signed off for the current neutral
fixture scope.

Open follow-up:

- stable relation reuse with qualified refs beyond alias-boundary fixtures.

## Non-Scope

- Reopening the unresolved cross-side lexical-scope contract before Java and
  Python agree on fail-closed behavior.
- Large compose runtime rewrites.
- Odoo business-model fixtures.

## Acceptance

- Fixture cases remain engine-neutral.
- Python replay validates SQL markers, forbidden markers, params, and error
  code/message markers.
- Any unsupported ambiguity is recorded as fail-closed rather than silently
  compiling.
- Closed for the current alias-boundary scope by
  [P0-42 progress](../progress/P0-42-compose-union-source-alias-shadowing-snapshot-replay-progress.md)
  and
  [P0-37 acceptance](../acceptance/P0-37-compose-source-alias-qualified-ref-snapshot-expansion-acceptance.md).
