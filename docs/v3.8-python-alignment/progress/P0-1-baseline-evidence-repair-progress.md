# P0-1 Baseline Evidence Repair Progress

Date: 2026-06-06

## Scope

Repair Python baseline blockers that were evidence/profile issues rather than
known engine behavior gaps.

In scope:

- Formula Java catalog path drift.
- External DB profile gating for conditional aggregate IF real DB tests.
- Focused and full pytest evidence.

Out of scope:

- Java snapshot generation changes.
- Odoo model registry resync.
- Production engine behavior changes.

## Work Items

| Ticket | Status | Summary |
| --- | --- | --- |
| `BUG-P0-1A` | closed | Formula parity catalog path pointed to old Java sibling repo. |
| `BUG-P0-1B` | closed | PostgreSQL real DB tests failed when optional local profile was unavailable. |

## Changes

| Path | Change |
| --- | --- |
| `tests/integration/test_formula_parity.py` | Resolve Java formula catalog through `FOGGY_JAVA_WORKTREE`, then current local Java worktree `foggy-data-mcp-bridge-wt-dev-compose`, then legacy sibling `foggy-data-mcp-bridge`. |
| `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py` | Add MySQL/PostgreSQL `SELECT 1` probe and skip unavailable external DB profile with an explicit reason. |

## Focused Verification

```bash
.venv/bin/python -m ruff check tests/integration/test_formula_parity.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py
```

Result:

```text
All checks passed!
```

```bash
.venv/bin/python -m pytest tests/integration/test_formula_parity.py -q --tb=short
```

Result:

```text
50 passed
```

```bash
.venv/bin/python -m pytest tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q --tb=short -rs
```

Result:

```text
12 passed, 4 skipped
SKIPPED [4] PostgreSQL demo database unavailable: Connect call failed ... 15432
```

## Full Baseline

```bash
.venv/bin/python -m pytest --tb=short -q -rs
```

Result:

```text
4095 passed, 162 skipped, 43 warnings in 17.44s
```

Notes:

- The previous 7 failures are gone.
- PostgreSQL conditional aggregate IF cases now skip when `localhost:15432` is
  unavailable.
- Other skipped tests are existing optional external DB or Java-resource lanes.

## Execution Check-In

Status: ready for acceptance.

Self-check:

- [x] Existing Java/Python/registry dirty work was not reverted or cleaned.
- [x] Production engine behavior was not changed.
- [x] Formula parity evidence path now resolves the active Java worktree.
- [x] Optional external DB profile failure is represented as skip with reason.
- [x] Focused and full pytest evidence recorded.
