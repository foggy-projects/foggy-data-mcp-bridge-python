# P0-52 Compose Snapshot Coverage Inventory Progress

## 2026-06-10

Status: complete.

Changes:

- Added `scripts/summarize-compose-snapshot-coverage.py` to produce a
  deterministic dialect/plan/status matrix from the Java compose snapshot
  fixture.
- The script validates that every successful compose snapshot has strict
  SQL-shape replay.
- Added `tests/integration/test_compose_snapshot_coverage_script.py` to keep
  the coverage inventory executable.
- The current inventory reports `16/16` strict success coverage and surfaces
  missing success cells for future targeted expansion, including SQLite base
  and MySQL8 join.

Evidence:

- Coverage inventory passed:
  `.venv/bin/python scripts/summarize-compose-snapshot-coverage.py`, reporting
  `caseCount 20`, `successCaseCount 16`, `strictSuccessCaseCount 16`, and
  `successStrictCoverage 16/16`.
- Focused replay and manifest passed:
  `.venv/bin/python -m pytest tests/integration/test_compose_snapshot_coverage_script.py tests/integration/test_java_compose_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  with `7 passed in 0.72s`.
- Ruff passed:
  `.venv/bin/ruff check scripts/summarize-compose-snapshot-coverage.py tests/integration/test_compose_snapshot_coverage_script.py`.
- `git diff --check` passed.

Follow-up:

- Use this inventory to pick targeted Java exporter expansions only when they
  add meaningful dialect/plan evidence.
