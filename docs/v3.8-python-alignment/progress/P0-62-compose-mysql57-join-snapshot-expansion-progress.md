# P0-62 Progress - Compose MySQL 5.7 Join Snapshot Expansion

Version: v3.8 Python alignment
Status: coding complete

## Development

- Added Java exporter case `join-mysql57-subquery` in
  `JavaComposeSnapshotTest`.
- Refreshed
  `tests/fixtures/java_compose_snapshot_parity.json` from the Java exporter.
- Updated Python coverage inventory assertions to require at least `28` cases,
  at least `24` successful cases, full strict success coverage, and no missing
  `mysql/join` success cell.
- Updated the Java snapshot parity manifest with MySQL 5.7 join subquery
  fallback evidence.

## Verification

- `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaComposeSnapshotTest`
  - Result: passed.
- `.venv/bin/python scripts/summarize-compose-snapshot-coverage.py`
  - Result: `28` cases, `24/24` strict successful cases.
- `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - Result: `7 passed in 0.57s`.
- `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`
  - Result: passed.
- `git diff --check`
  - Result: passed for Java and Python worktrees.

## Remaining Gaps

- SQLite `derived/union/join` staged compose lane.

## Self-Check

- Production compiler behavior changed: no.
- Java/Python snapshot fixture refreshed from exporter: yes.
- Live DB execution added: no.
- Odoo generated models touched: no.
- Registry bundle changed: no.
- Untracked Python `charts/` staged: no.
