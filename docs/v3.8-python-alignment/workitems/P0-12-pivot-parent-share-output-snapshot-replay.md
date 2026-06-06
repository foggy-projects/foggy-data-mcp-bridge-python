# P0-12 Pivot ParentShare Output Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active real SQLite Pivot output snapshot lane with Java-produced
`parentShare` output cases, replayed in Python over the same neutral seed.

This item stays on the ordinary two-level row-axis Pivot path:

- flat rows with native metric plus `parentShare`
- grid rows + columns with native metric plus `parentShare`

`baselineRatio`, non-additive auxiliary requery, tree/cascade behavior, and
Odoo domain fixtures remain separate follow-up work.

## Java Current Contract

Java supports mixed Pivot metrics through the public `metrics` array:

- native metric shorthand, for example `"salesAmount"`
- derived metric object, for example
  `{"name":"share","type":"parentShare","of":"salesAmount"}`

For an implicit two-level row hierarchy, Java computes `parentShare` as the
current child metric divided by the parent aggregate metric. Sparse grid cells
without a numerator or denominator emit `null`.

## Python Gap

Python already had `semantic/pivot/parent_share.py` and unit coverage for
ordinary row-axis `parentShare`, grand-total null behavior, and grid output.
The active Java output snapshot replay did not yet prove this against the
current Java engine output contract.

The only replay harness gap found in this item was flat canonicalization:
Python replay compared native `sales` but did not include the Java `share`
metric field for flat output.

## Implementation Scope

Production code:

- No production engine change is planned for this workitem unless replay exposes
  a real engine mismatch.

Java snapshot producer:

- `JavaPivotOutputSnapshotTest.java`
  - add a second electronics subcategory to the isolated seed so `parentShare`
    has non-trivial `0.75` and `0.25` shares
  - add flat and grid `parentShare` output cases
  - keep the seed neutral and scoped by `order_status`

Python replay:

- `tests/integration/test_java_pivot_output_snapshot_parity.py`
  - detect object metrics by `name`
  - include `share` in flat canonical rows when requested

Python fixture:

- `tests/fixtures/java_pivot_output_snapshot_parity.json`
  - now contains ten cases, including flat/grid `parentShare` output cases

## Acceptance

Required focused checks:

- Java exporter passes with SQLite profile:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- Python replay passes:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- P0 manifest and affected Pivot lanes pass:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_parent_share.py -q`

## Follow-Ups

- Add baselineRatio output snapshot cases.
- Add non-additive auxiliary requery snapshot cases.
- Add large-domain threshold/fail-closed snapshot cases.
- Add pivot/domain governance propagation snapshots.
