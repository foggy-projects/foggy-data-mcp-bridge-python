# P0-14 Pivot Non-Additive Output Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active real SQLite Pivot output snapshot lane with Java-aligned
ordinary non-additive total rows and make Python replay them through the engine.

This item stays on the ordinary flat Pivot path:

- two-level row axis
- `rowSubtotals=true`
- `grandTotal=true`
- mixed additive `salesAmount` plus non-additive `uniqueCustomers`

Grid non-additive totals, cascade/tree semantics, large-domain refusal, and
Odoo business fixtures remain separate follow-up work.

## Java Current Contract

Java Pivot V9 treats non-additive aggregations such as `COUNT_DISTINCT` as
requiring auxiliary requery for generated subtotal and grand-total rows. In the
neutral ecommerce fixture, two Electronics leaf rows share one customer, so the
Electronics subtotal must report `uniqueCustomers=1`, not the additive sum `2`.
The grand total must report the distinct count across the full slice.

## Python Gap

Before this workitem, Python ordinary Pivot generated row subtotal and grand
total rows by reusing the additive totals path. That is correct for `SUM` and
`COUNT`, but it over-counts `COUNT_DISTINCT` and is not a valid implementation
for `AVG`, `MIN`, `MAX`, or other non-additive aggregations.

## Implementation Scope

Production code:

- `src/foggy/dataset_model/semantic/pivot/non_additive_totals.py`
  - detect native Pivot metrics whose model measure aggregation is not
    `sum` or `count`
  - requery row subtotals at parent row grain plus column grain
  - requery grand totals at column grain
  - overwrite only generated total rows marked by `_sys_meta`
  - fail closed if an auxiliary query returns an error or misses a required
    generated total row
- `src/foggy/dataset_model/semantic/service.py`
  - apply non-additive auxiliary totals after ordinary subtotal/grandTotal row
    generation and before derived metric/grid shaping

Java snapshot producer:

- `JavaPivotOutputSnapshotTest.java`
  - add `pivot-flat-rows-subtotals-grand-total-non-additive`
  - seed customer keys so additive subtotal would be observably wrong

Python replay:

- `tests/integration/test_java_pivot_output_snapshot_parity.py`
  - seed `customer_key`
  - canonicalize `uniqueCustomers` in flat output

Python fixture:

- `tests/fixtures/java_pivot_output_snapshot_parity.json`
  - now contains thirteen cases, including the non-additive row subtotal and
    grand-total output case

## Acceptance

Required focused checks:

- Java exporter target:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaPivotOutputSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- Scoped lint:
  `.venv/bin/python -m ruff check src/foggy/dataset_model/semantic/pivot/non_additive_totals.py tests/integration/test_java_pivot_output_snapshot_parity.py`

## Current Verification

Passed:

- Java exporter:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python focused replay:
  `2 passed in 0.43s`
- Scoped ruff for the new helper and replay test:
  `All checks passed!`
- Full Python pytest baseline:
  `4041 passed, 232 skipped, 43 warnings in 17.50s`

## Follow-Ups

- Add non-additive grid output snapshots if Java contract requires grid totals
  to be proven separately.
- Keep cascade/tree non-additive totals out of P0 unless Java exports a small
  neutral fixture and Python already has an equivalent low-risk path.
- Add large-domain threshold/fail-closed snapshots.
- Add pivot/domain governance propagation snapshots.
