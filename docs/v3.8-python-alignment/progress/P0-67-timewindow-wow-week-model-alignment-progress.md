# P0-67 Progress - TimeWindow WoW Week Model Alignment

## Document Purpose

- doc_type: progress
- intended_for: execution-agent, reviewer
- purpose: Record implementation, verification, and self-check status for closing the timeWindow `wow-week-happy` Java model/catalog drift.

Version: v3.8 Python alignment
Status: coding complete

## Development Progress

- Added Java ecommerce `salesDate$week` as logical property `week` backed by
  physical column `week_of_year`.
- Added `fs.salesDate$week` to Java ecommerce `FactSalesQueryModel`.
- Tightened Java `TimeWindowParitySnapshotTest` to require all 9 timeWindow
  catalog happy cases as SQL snapshots and to fail on any generation error.
- Refreshed Python
  `tests/integration/_time_window_parity_snapshot.json` from the Java exporter;
  it now contains 9 snapshots and `generation_errors: []`.
- Updated Python golden diff replay to require 9 Java-success cases and no
  expected Java generation errors.
- Added the same `week` logical property and query exposure to Python FSScript
  ecommerce fixtures for loader-path consistency.
- Updated the Java snapshot parity manifest and v3.8 alignment docs.

## Testing Progress

- `mvn test -P!multi-db -pl foggy-dataset-model -am -Dtest=TimeWindowParitySnapshotTest -Dsurefire.failIfNoSpecifiedTests=false`
  - Result: passed.
- `.venv/bin/python -m pytest tests/integration/test_time_window_golden_diff.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/integration/test_java_snapshot_parity_manifest.py tests/test_dataset_model/test_loader_fsscript.py -q`
  - Result: `94 passed in 2.47s`.
- `.venv/bin/ruff check tests/integration/test_time_window_golden_diff.py tests/integration/test_java_snapshot_parity_manifest.py`
  - Result: passed.

## Experience Progress

- N/A. This is backend engine fixture, snapshot, and test alignment with no UI
  or manual interaction surface.

## Execution Check-In

- Completed work summary: the Java/Python ecommerce timeWindow fixture now
  exposes `salesDate$week`; Java exports `wow-week-happy` as a normal SQL
  snapshot; Python replay treats all 9 happy cases as active parity evidence.
- Touched code paths:
  - Java demo TM/QM fixture.
  - Java `TimeWindowParitySnapshotTest`.
  - Python demo TM/QM fixture.
  - Python timeWindow golden diff test.
  - Python Java snapshot parity fixture and manifest.
  - Python v3.8 alignment docs.
- Remaining risks:
  - Full normalized SQL diff is still deferred for multi-CTE timeWindow SQL.
  - Live DB/result parity is still a follow-up beyond existing SQLite
    execution tests.

## Self-Check

- Requirement scope implemented as intended: yes.
- Non-goals accidentally expanded: no.
- Odoo generated models touched: no.
- Registry bundle changed: no.
- Untracked Python `charts/` staged: no.
- Basic self-review completed: yes.
- Test status recorded: pass.
- Formal quality gate required before acceptance: no, this is a narrow fixture
  and test alignment item; focused tests and docs are sufficient.
