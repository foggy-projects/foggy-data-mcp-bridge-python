# P0-11 Pivot RowSubtotals Output Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active P0-8/P0-10 real SQLite Pivot output snapshot lane with
Java-produced two-level row subtotal output cases, replayed in Python without
Odoo business models.

This item stays on the ordinary additive Pivot path:

- flat two-level rows + metric + `options.rowSubtotals + grandTotal`
- grid two-level rows + columns + metric + `options.rowSubtotals + grandTotal`

`parentShare`, `baselineRatio`, non-additive auxiliary requery, and Odoo domain
fixtures remain separate follow-up work.

## Java Current Contract

Java emits row subtotal rows when `PivotOptions.rowSubtotals=true` and the row
axis has more than one level.

Observed public output contract from the Java snapshot producer:

- row subtotal leaf-axis members use `ALL`
- grand total row-axis members use `GRAND_TOTAL`
- row subtotal rows carry `_sys_meta.isRowSubtotal=true`
- grand total rows carry `_sys_meta.isGrandTotal=true`
- grid output exposes subtotal/grand-total members through `rowHeaders` and
  the corresponding cells

## Python Gap

Python ordinary Pivot had a grandTotal post-processing path, but did not append
two-level row subtotal rows for ordinary flat/grid output. Java snapshot replay
therefore failed on the first `rowSubtotals + grandTotal` case: Python returned
only leaf rows and grand total, while Java returned leaf rows, per-parent
subtotal rows, and grand total.

## Implementation Scope

Production code:

- `src/foggy/dataset_model/semantic/service.py`
  - when ordinary Pivot enables `rowSubtotals`, reuse the existing additive
    totals helper before flat/grid output shaping
  - keep the previous grandTotal-only path unchanged when `rowSubtotals` is not
    enabled

Java snapshot producer:

- `JavaPivotOutputSnapshotTest.java`
  - add two-level row subtotal output cases
  - extend the neutral seed contract with `subCategory`

Python replay:

- `tests/integration/test_java_pivot_output_snapshot_parity.py`
  - seed `dim_product.sub_category_id/sub_category_name`
  - canonicalize optional `subCategory` members for flat/grid output

Python fixture:

- `tests/fixtures/java_pivot_output_snapshot_parity.json`
  - now contains eight cases: three base flat/grid cases, three grandTotal
    cases, and two rowSubtotals + grandTotal cases

## Acceptance

Required focused checks:

- Java exporter passes with SQLite profile:
  `mvn clean test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- Python replay passes:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- P0 manifest and affected Pivot lanes pass:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareGrandTotal -q`

## Follow-Ups

- Add parentShare output snapshot cases.
- Add baselineRatio output snapshot cases.
- Add non-additive auxiliary requery snapshot cases.
- Add large-domain threshold/fail-closed snapshot cases.
- Add pivot/domain governance propagation snapshots.
