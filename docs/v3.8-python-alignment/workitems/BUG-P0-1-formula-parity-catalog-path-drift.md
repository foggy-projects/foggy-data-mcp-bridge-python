---
type: bug
bug_source: regression-found
version: v3.8-python-alignment
ticket: BUG-P0-1A
severity: major
status: closed
reproduction_status: confirmed
test_strategy: integration-test
automation_decision: required
owner: python-engine
---

# BUG P0-1A: Formula Parity Catalog Path Drift

## Background

During the Python alignment baseline run, formula parity tests failed before
they could compare Java/Python formula output. The committed Java snapshot was
present, but the shared Java formula catalog was not loaded.

The test still looked for the old sibling repo name `foggy-data-mcp-bridge`.
The current Java worktree for this alignment line is
`foggy-data-mcp-bridge-wt-dev-compose`.

## Reproduction

Command:

```bash
.venv/bin/python -m pytest tests/integration/test_formula_parity.py -q --tb=short
```

Before the fix, the full-suite failures were:

- `test_catalog_has_coverage_targets`
- `test_committed_snapshot_not_hand_edited`
- `test_parity_matches_java_snapshot`

The observed shape was catalog size `0` with committed snapshot entries still
present, causing orphan snapshot ids such as `ari-*`, `cmp-*`, `bool-*`, and
`agg-*`.

## Expected vs Actual

Expected:

- Python resolves the Java formula catalog from the current Java worktree.
- Catalog and committed Java snapshot can be compared.
- Missing Java worktree should skip with a clear message, not create false
  orphan failures.

Actual:

- Catalog path pointed to a non-existent old sibling repo.
- `_CATALOG` became empty.
- Snapshot integrity tests failed with misleading orphan ids.

## Impact Scope

- Affects Python alignment baseline evidence.
- Does not indicate formula compiler behavior drift by itself.
- Blocks confidence in Java/Python formula parity until fixed.

## Test Strategy

Automated integration test is required because this is a cross-repo fixture
contract.

Covered by:

```bash
.venv/bin/python -m pytest tests/integration/test_formula_parity.py -q --tb=short
```

## Code Inventory

- `tests/integration/test_formula_parity.py`

## Fix Checklist

- [x] Resolve catalog via explicit `FOGGY_JAVA_WORKTREE` when provided.
- [x] Resolve current local Java worktree
  `foggy-data-mcp-bridge-wt-dev-compose`.
- [x] Keep backward compatibility with old sibling name
  `foggy-data-mcp-bridge`.
- [x] Preserve skip behavior when no Java catalog exists.
- [x] Run focused formula parity test.
- [x] Run full Python baseline after P0-1B is also fixed.

## Verification

Focused verification:

```bash
.venv/bin/python -m pytest tests/integration/test_formula_parity.py -q --tb=short
```

Result:

```text
50 passed
```

Full baseline after P0-1A and P0-1B:

```bash
.venv/bin/python -m pytest --tb=short -q -rs
```

Result:

```text
4095 passed, 162 skipped, 43 warnings
```
