---
type: bug
bug_source: regression-found
version: v3.8-python-alignment
ticket: BUG-P0-1B
severity: major
status: closed
reproduction_status: confirmed
test_strategy: integration-test
automation_decision: required
owner: python-engine
---

# BUG P0-1B: PostgreSQL Real DB Profile Gate Missing

## Background

The Python alignment baseline failed in conditional aggregate IF real DB tests
when local PostgreSQL was not running at `localhost:15432`.

Other Python integration matrices already follow the convention that optional
external DB profiles skip when unavailable and only assert parity after a
successful probe. This test file did not have that gate.

## Reproduction

Command:

```bash
.venv/bin/python -m pytest tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q --tb=short
```

When PostgreSQL is not running at `localhost:15432`, four parameterized
PostgreSQL cases fail with connection refused:

```text
Connect call failed ('::1', 15432, 0, 0)
Connect call failed ('127.0.0.1', 15432)
```

## Expected vs Actual

Expected:

- SQLite coverage always runs.
- MySQL/PostgreSQL real DB parity runs only after a successful demo DB probe.
- Missing local DB profile is reported as skipped with a clear reason.

Actual:

- PostgreSQL execution path failed the whole baseline when the local profile was
  unavailable.

## Impact Scope

- Affects local and CI baseline stability.
- Does not indicate conditional aggregate IF behavior drift by itself.
- Can hide real engine regressions by making the suite fail on environment
  availability first.

## Test Strategy

Automated integration-test gate is required because the issue is deterministic
when the external DB profile is missing.

Covered by:

```bash
.venv/bin/python -m pytest tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q --tb=short -rs
```

## Code Inventory

- `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py`

## Fix Checklist

- [x] Add lightweight `SELECT 1` probe before yielding MySQL service.
- [x] Add lightweight `SELECT 1` probe before yielding PostgreSQL service.
- [x] Close executor before skipping an unavailable external DB profile.
- [x] Preserve SQLite and governance tests as always-on coverage.
- [x] Run focused conditional aggregate IF suite.
- [x] Run full Python baseline after P0-1A is also fixed.

## Verification

Focused verification:

```bash
.venv/bin/python -m pytest tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q --tb=short -rs
```

Result in the current local environment:

```text
12 passed, 4 skipped
SKIPPED [4] PostgreSQL demo database unavailable: Connect call failed ... 15432
```

Full baseline after P0-1A and P0-1B:

```bash
.venv/bin/python -m pytest --tb=short -q -rs
```

Result:

```text
4095 passed, 162 skipped, 43 warnings
```
