# P0-8 Pivot Output SQLite Snapshot Replay

Date: 2026-06-06

## Objective

Activate a real result-output Java snapshot lane for Python Pivot alignment.
This slice stays engine-neutral and uses an isolated SQLite seed instead of
Odoo business models.

## Scope

- Java snapshot producer:
  - `JavaPivotOutputSnapshotTest.java`
- Python fixture:
  - `tests/fixtures/java_pivot_output_snapshot_parity.json`
- Python replay:
  - `tests/integration/test_java_pivot_output_snapshot_parity.py`
- Manifest lane:
  - `pivot-output-sqlite-snapshots`

## Contracts Covered

- Real Java Pivot flat output for row dimensions and native metric totals.
- Real Java Pivot flat output for row plus column dimensions.
- Real Java Pivot grid output for row plus column dimensions.
- Sparse grid cell behavior where missing row/column intersections are `null`.
- Python replay over the same isolated category/year/sales seed in SQLite.

## Out Of Scope

- Odoo domain models and registry bundle updates.
- Subtotal and grand-total output parity.
- `parentShare` output parity.
- `baselineRatio` output parity.
- Non-additive auxiliary requery output parity.
- Production engine code changes.

## Known Gap

The focused replay exposed a Python Pivot cache-key collision: when the same
`SemanticQueryService` instance executes flat rows+columns and grid rows+columns
requests with the same axes and metrics, the translated non-pivot request can
collide in cache before output shaping. The replay uses a fresh service per
case to keep snapshot evidence active without changing production code in this
slice.

## Acceptance

- Java producer writes the committed Python fixture and passes focused Maven
  execution against SQLite.
- Python replay and manifest tests pass.
- Ruff passes for the new Python replay.
- Any environment failure, such as missing real DB services, is recorded.
