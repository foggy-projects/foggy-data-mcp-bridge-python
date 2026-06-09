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
- dropped-column source alias refusal,
- SQL Server derived-chain fallback guard against `FROM (WITH`.

Python replay is anchored by:

- `tests/fixtures/java_compose_snapshot_parity.json`
- `tests/integration/test_java_compose_snapshot_parity.py`
- `tests/compose/compilation/test_join.py`

## Remaining Expansion

Add or refresh Java snapshots for:

- nested derived source alias inheritance after join,
- side-qualified and source-qualified refs in `slice`, `orderBy`, and
  projection,
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
