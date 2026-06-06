# P0-9 Pivot Output Cache Key Collision Progress

Date: 2026-06-06

## Progress

- Created BUG-P0-9 workitem from the P0-8 replay finding.
- Activated same-service P0-8 flat/grid replay over one SQLite seed and one
  cached `SemanticQueryService`.
- Confirmed the regression before the fix:
  `tests/integration/test_java_pivot_output_snapshot_parity.py::test_java_pivot_output_snapshot_replays_in_python`
  failed because the grid case received the previous flat rows+columns cached
  response.
- Updated `SemanticQueryService.query_model` so the original Pivot request
  shape is captured before Pivot translation and included in the execute cache
  key.
- Kept dictionary discovery changes in `semantic/service.py` intact; the P0-9
  production edit is limited to Pivot cache-key isolation.

## Verification

- Reproduction before fix:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q --tb=short`
  -> `1 failed, 1 passed`.
- Focused replay after fix passed:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q --tb=short`
  -> `2 passed in 0.46s`.
- P0-7/P0-8 replay, manifest, and existing Pivot grid tests passed:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py tests/test_dataset_model/test_pivot_v9_grid.py -q --tb=short`
  -> `14 passed in 0.51s`.
- Ruff passed for the touched replay/manifest tests:
  `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`.
- Ruff on the full `src/foggy/dataset_model/semantic/service.py` remains
  blocked by existing broad style/import modernization findings; this was not
  auto-fixed to avoid unrelated churn in a user-dirty file.
- Full pytest was attempted and hit the known intermittent compose suspend
  cleanup area:
  `.venv/bin/python -m pytest --tb=short -q -rs`
  -> `1 failed, 4110 passed, 162 skipped, 43 warnings in 17.47s`.
- The failing test passed when rerun directly:
  `.venv/bin/python -m pytest tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_reject -q --tb=short`
  -> `1 passed in 0.03s`.

## Follow-Up

- Keep subtotal, grand-total, `parentShare`, `baselineRatio`, and non-additive
  output snapshots as separate Pivot output lanes.
