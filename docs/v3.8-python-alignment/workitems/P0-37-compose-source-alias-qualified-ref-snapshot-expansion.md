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
- dropped-column source alias refusal,
- SQL Server derived-chain fallback guard against `FROM (WITH`.

Python replay is anchored by:

- `tests/fixtures/java_compose_snapshot_parity.json`
- `tests/integration/test_java_compose_snapshot_parity.py`
- `tests/compose/compilation/test_join.py`

## Completed Expansion

Added Java snapshot cases:

- `qualified-source-alias-slice-order-postgres`
- `inherited-source-alias-through-derived-postgres`

The Python replay harness now reconstructs derived snapshot nodes through
`QueryPlan.query(...)` instead of direct `from_(source=...)` construction, so
replay uses the same compose alias propagation path as production callers.

## Remaining Expansion

Add or refresh Java snapshots for:

- ambiguous duplicate source alias refusal,
- source alias shadowing by projected column alias refusal,
- union-as-source and stable relation reuse with qualified refs,
- dialect markers for MySQL, PostgreSQL, and SQL Server fallback shape.

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
