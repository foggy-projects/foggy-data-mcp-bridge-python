# S3 — Normalized SQL Golden Diff Harness Progress

**Status**: complete (partial — timeWindow full SQL diff awaits Java snapshot producer)
**Stage**: 3 of P2 post-v1.5 follow-up execution plan

## Development Progress

### Completed

1. **`_golden_sql_diff.py` helper** — reusable golden diff framework
   - `GoldenCase` dataclass: feature, case_id, dialect, expected/actual SQL+params, source_hint
   - `GoldenMismatch` structured output with summary formatter
   - `GoldenDiffResult` aggregate with `ok` property and `failure_message()`
   - `compare_golden_cases()` / `assert_golden_cases()` bulk compare
   - Delegates normalization to existing `_sql_normalizer.to_canonical`

2. **Formula lane migration** — `test_formula_parity.py::test_parity_matches_java_snapshot`
   - Refactored to use `assert_golden_cases` instead of inline mismatch loop
   - All 50 existing tests pass (0 regressions)
   - Catalog, snapshot schema, integrity, coverage tests unchanged

3. **TimeWindow lane** — `test_time_window_golden_diff.py`
   - Structural parity for 2 post-scalar calculatedFields cases:
     - `yoy-month-post-calc-growth-happy`
     - `rolling_7d-post-calc-gap-happy`
   - Verifies: expected columns, post-calc FROM wrapper, comparative CTE, tw_result references
   - Full golden SQL diff path ready — activates when `_time_window_parity_snapshot.json` exists
   - Skips with documented message when snapshot absent

### Gap

Java timeWindow fixtures (`java_time_window_parity_catalog.json`) contain structural assertions but **not** full normalized SQL golden output. A `TimeWindowParitySnapshotTest` (analogous to `FormulaParitySnapshotTest`) would be needed to produce normalized SQL for the full golden diff path.

This is intentionally deferred — building the timeWindow snapshot producer requires standing up the full `SemanticQueryService` test context, which is significantly heavier than the formula snapshot (which only uses `CalculatedFieldService.compileExpression`).

## Testing Progress

```
Formula parity:    50 passed in 0.25s
TimeWindow golden: 2 passed, 1 skipped in 0.22s
Focused regression: 69 passed, 1 skipped in 0.27s
```

The 1 skipped test is `test_full_golden_diff_when_snapshot_available` — expected, since no Java timeWindow SQL snapshot exists yet.

## Experience Progress

N/A — this is backend test infrastructure with no UI interaction surface.

## Touched Files

### Python repo (`foggy-data-mcp-bridge-python`)

| File | Change |
|------|--------|
| `tests/integration/_golden_sql_diff.py` | **NEW** — reusable golden diff helper |
| `tests/integration/test_formula_parity.py` | Refactored snapshot compare to use helper |
| `tests/integration/test_time_window_golden_diff.py` | **NEW** — timeWindow structural + golden diff |
| `docs/v1.5/S3-normalized-sql-golden-diff-progress.md` | **NEW** — this file |
| `docs/v1.5/P2-post-v1.5-followup-execution-plan.md` | Updated Stage 3 status |

### Java repo (`foggy-data-mcp-bridge-wt-dev-compose`)

No changes.

## Commands Run

```
python -m pytest tests/integration/test_formula_parity.py -q → 50 passed
python -m pytest tests/integration/test_time_window_golden_diff.py -q → 2 passed, 1 skipped
python -m pytest tests/integration/test_formula_parity.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/integration/test_time_window_golden_diff.py -q → 69 passed, 1 skipped
git diff --check → clean
```

## Remaining Risks

1. **Java timeWindow SQL snapshot producer** — needed for full golden diff on timeWindow lane. Documented gap, not a blocker for Stage 3 acceptance.
2. **CI workflow** — harness is local-only; external CI wiring (Stage 2 assumption) still pending.
3. **Future lanes** — compose, broader timeWindow, CTE lanes can plug into the harness by adding new `GoldenCase` loaders.

## Coverage Audit / Quality Gate

Not recommended at this stage — the harness is test infrastructure, not shared compiler behavior. The formula lane's existing quality gate (S1-S2) covers the normalization rules. A quality gate would be appropriate when:
- The Java timeWindow SQL snapshot producer is added
- A new feature lane is added that changes normalization rules
