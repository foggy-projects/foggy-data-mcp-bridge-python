# P0-66 Progress - TimeWindow Current Java Snapshot Refresh

Version: v3.8 Python alignment
Status: coding complete

## Development

- Expanded Java `TimeWindowParitySnapshotTest` from 2 post-scalar cases to the
  full current catalog happy-case pass.
- Added Java snapshot generation error recording for the current
  `wow-week-happy` drift:
  `FactSalesQueryModel` lacks `salesDate$week`.
- Refreshed
  `tests/integration/_time_window_parity_snapshot.json` with 8 SQL snapshots
  and 1 generation error.
- Updated Python `test_time_window_golden_diff.py` to require the current Java
  success/error coverage and replay every Java-success case through Python
  validate mode.
- Updated the Java snapshot parity manifest and v3.8 alignment matrix.

## Verification

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=TimeWindowParitySnapshotTest`
  - Result: passed.
- `.venv/bin/python -m pytest tests/integration/test_time_window_golden_diff.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/test_dataset_model/test_time_window_sqlite_execution.py -q`
  - Result: `28 passed in 0.64s`.

## Remaining Gaps

- Java current `FactSalesQueryModel` and the legacy timeWindow catalog still
  disagree on `wow-week-happy` because `salesDate$week` is not present.
- Full normalized SQL diff remains deferred for multi-CTE timeWindow SQL.
- Live DB/result parity beyond the existing SQLite execution tests remains a
  follow-up.

## Self-Check

- Production compiler behavior changed: no.
- Java/Python snapshot fixture refreshed from exporter: yes.
- Current Java generation drift recorded instead of hidden: yes.
- Live DB execution added: no.
- Odoo generated models touched: no.
- Registry bundle changed: no.
- Untracked Python `charts/` staged: no.
