# P0-10 Pivot GrandTotal Output Snapshot Replay

Date: 2026-06-06

## Goal

Extend the P0-8 real SQLite Pivot output snapshot lane with Java-produced
`grandTotal` output cases and replay them in Python without Odoo business
models.

This work item intentionally stays on the low-risk ordinary Pivot path:

- flat rows + metric + `options.grandTotal`
- flat rows + columns + metric + `options.grandTotal`
- grid rows + columns + metric + `options.grandTotal`

Two-level cascade row subtotal snapshots, non-additive auxiliary requery, and
Odoo domain fixtures remain separate follow-up work.

## Java Current Contract

Java `PivotPipeline` injects grand total rows through `SubtotalInjector` when
`PivotOptions.grandTotal=true`.

Observed public output contract from the Java snapshot producer:

- grand total row-axis members use `GRAND_TOTAL`
- row subtotal members use `ALL`
- grand total rows carry `_sys_meta.isGrandTotal=true`
- with a column axis, Java emits one grand-total row per surviving column member
- grid output exposes the grand-total member through `rowHeaders` and the
  corresponding cells

## Python Gap

Python ordinary Pivot already had a grandTotal post-processing path, but it
shared the cascade subtotal helper's `ALL` member marker for grand totals.
That differed from Java's public output marker.

## Implementation Scope

Production code:

- `src/foggy/dataset_model/semantic/pivot/cascade_totals.py`
  - keep row subtotal marker as `ALL`
  - use `GRAND_TOTAL` for grandTotal row-axis members

Java snapshot producer:

- `JavaPivotOutputSnapshotTest.java`
  - add three `grandTotal` output cases
  - include request `options` in the exported fixture contract

Python replay:

- `tests/integration/test_java_pivot_output_snapshot_parity.py`
  - pass snapshot `options` into `SemanticQueryRequest.pivot`
  - compare Java/Python canonical output directly, without normalizing
    `GRAND_TOTAL`

Python fixture:

- `tests/fixtures/java_pivot_output_snapshot_parity.json`
  - now contains six cases: three P0-8 base flat/grid cases plus three P0-10
    grandTotal cases

## Acceptance

Required focused checks:

- Java exporter passes with SQLite profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- Python replay and affected grandTotal helpers pass:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_cascade_totals.py tests/test_dataset_model/test_pivot_parent_share.py::TestParentShareGrandTotal -q`
- P0 manifest and Pivot snapshot lanes pass:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py -q`

## Follow-Ups

- Export Java two-level rowSubtotals + grandTotal output snapshots and replay
  them against Python cascade totals.
- Add parentShare output snapshot cases.
- Add baselineRatio output snapshot cases.
- Add non-additive auxiliary requery snapshot cases.
- Add large-domain threshold/fail-closed snapshot cases.
