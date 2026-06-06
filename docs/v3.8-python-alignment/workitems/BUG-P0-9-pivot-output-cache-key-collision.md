---
type: bug
bug_source: regression-found
version: v3.8-python-alignment
ticket: BUG-P0-9
severity: major
status: ready-for-verification
reproduction_status: confirmed
test_strategy: integration-test
automation_decision: required
owner: python-engine
---

# BUG-P0-9 Pivot Output Cache Key Collision

## Background

P0-8 activated Java real Pivot output replay for Python. During focused replay,
running flat rows+columns and grid rows+columns requests on the same
`SemanticQueryService` instance exposed a cache collision: both requests are
translated into the same non-pivot query before the cache key is generated.

## Reproduction

Use the P0-8 fixture `tests/fixtures/java_pivot_output_snapshot_parity.json`
and execute the flat rows+columns case followed by the grid rows+columns case
on one cached `SemanticQueryService` instance.

## Expected vs Actual

- Expected: flat and grid Pivot requests with identical axes and metrics keep
  separate cached responses because `outputFormat` changes response shape.
- Actual: the grid request can receive the cached flat response because the
  cache key is based on the translated non-pivot request only.

## Impact Scope

- Affects cached ordinary Pivot execution when output shape differs but the
  translated SQL request is identical.
- Confirmed for `flat` versus `grid`; `layout`, `options`, and Pivot sidecar
  semantics should be treated as cache-key inputs as well.
- Does not require Java changes; Java P0-8 exporter already proves the desired
  output contract.

## Test Strategy

Update the P0-8 integration replay to run flat/grid snapshot cases against one
service instance, then keep Java canonical output comparison unchanged.

## Code Inventory

- `src/foggy/dataset_model/semantic/service.py`
- `tests/integration/test_java_pivot_output_snapshot_parity.py`
- `docs/v3.8-python-alignment/progress/P0-9-pivot-output-cache-key-collision-progress.md`

## Fix Checklist

- [x] Add/activate same-service flat/grid replay regression.
- [x] Include original Pivot request shape in the query cache key.
- [x] Verify P0-8 replay, manifest, and ruff.
- [x] Keep unrelated dictionary discovery changes untouched except where the
  shared `service.py` edit is strictly necessary.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q --tb=short`
- `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q --tb=short`
- `.venv/bin/python -m ruff check tests/integration/test_java_pivot_output_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py`

## References

- P0-8 workitem: `docs/v3.8-python-alignment/workitems/P0-8-pivot-output-sqlite-snapshot-replay.md`
- Java exporter: `JavaPivotOutputSnapshotTest`
