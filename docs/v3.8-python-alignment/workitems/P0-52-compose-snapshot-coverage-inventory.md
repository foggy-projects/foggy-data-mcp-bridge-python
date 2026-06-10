# P0-52 Compose Snapshot Coverage Inventory

## Requirement

Turn the current compose snapshot dialect and SQL-shape coverage into an
executable inventory before adding more golden SQL cases.

This keeps the next compose work grounded in the fixture that Java already
exports and Python already replays, instead of relying on ad hoc notes about
which dialect/plan cells are covered.

## Scope

- Read `tests/fixtures/java_compose_snapshot_parity.json`.
- Summarize case counts by dialect, plan type, status, and strict SQL-shape
  coverage.
- Fail closed if any successful compose snapshot is not strict on SQL shape.
- Surface missing success cells for the target dialect/plan matrix.
- Add a focused pytest wrapper so the inventory stays executable.

## Non-Goals

- Do not add new Java compose exporter cases in this step.
- Do not claim every missing dialect/plan cell is immediately required.
- Do not introduce live database execution or product-layer analysis.

## Acceptance

- `scripts/summarize-compose-snapshot-coverage.py` prints a deterministic JSON
  summary.
- The summary reports all current successful cases as strict SQL-shape replay.
- The summary exposes missing success cells such as SQLite compose snapshots
  and MySQL8 join coverage.
- Focused pytest coverage passes.
