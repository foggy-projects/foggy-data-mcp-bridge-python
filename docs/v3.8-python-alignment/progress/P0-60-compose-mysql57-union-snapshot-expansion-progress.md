# P0-60 Progress - Compose MySQL 5.7 Union Snapshot Expansion

Version: v3.8 Python alignment
Status: coding complete

## Development

- Added Java exporter case `union-all-sales-orders-mysql57` in
  `JavaComposeSnapshotTest`.
- Refreshed
  `tests/fixtures/java_compose_snapshot_parity.json` from the Java exporter.
- Updated Python coverage inventory assertions to require at least `26` cases,
  at least `22` successful cases, full strict success coverage, and no missing
  `mysql/union` success cell.
- Updated the Java snapshot parity manifest with MySQL 5.7 top-level union
  evidence.

## Verification

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  - Result: passed.
- `.venv/bin/python scripts/summarize-compose-snapshot-coverage.py`
  - Result: `26` cases, `22/22` strict successful cases.
- `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - Result: `7 passed in 0.75s`.
- `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
  - Result: passed.
- `git diff --check`
  - Result: passed for Java and Python worktrees.

## Remaining Gaps

- MySQL 5.7 `join` success cell.
- SQLite `base/derived/union/join` staged compose lane.

## Self-Check

- Production compiler behavior changed: no.
- Java/Python snapshot fixture refreshed from exporter: yes.
- Odoo generated models touched: no.
- Registry bundle changed: no.
- Untracked Python `charts/` staged: no.
