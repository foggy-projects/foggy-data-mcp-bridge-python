# P0-63 Progress - Compose SQLite Derived Snapshot Expansion

Version: v3.8 Python alignment
Status: coding complete

## Development

- Added Java exporter case `derived-filter-order-limit-sqlite-cte` in
  `JavaComposeSnapshotTest`.
- Refreshed
  `tests/fixtures/java_compose_snapshot_parity.json` from the Java exporter.
- Updated Python coverage inventory assertions to require at least `29` cases,
  at least `25` successful cases, full strict success coverage, and no missing
  `sqlite/derived` success cell.
- Updated the Java snapshot parity manifest with SQLite derived CTE evidence.

## Verification

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  - Result: passed.
- `.venv/bin/python scripts/summarize-compose-snapshot-coverage.py`
  - Result: `29` cases, `25/25` strict successful cases.
- `.venv/bin/python -m pytest tests/integration/test_java_compose_snapshot_parity.py -q`
  - Result: `2 passed in 0.48s`.
- `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - Result: `7 passed in 0.57s`.
- `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
  - Result: passed.

## Remaining Gaps

- SQLite `union/join` staged compose lane.

## Self-Check

- Production compiler behavior changed: no.
- Java/Python snapshot fixture refreshed from exporter: yes.
- Live DB execution added: no.
- Odoo generated models touched: no.
- Registry bundle changed: no.
- Untracked Python `charts/` staged: no.
