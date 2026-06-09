# P0-33 HAVING Aggregate Alias Strictness Progress

Date: 2026-06-09

## Completed

- Split explicit `request.having` from aggregate conditions auto-lifted from
  `slice`.
- Marked only explicit aggregate aliases as eligible for top-level HAVING alias
  resolution.
- Rejected direct ordinary aggregate-measure fields in explicit HAVING with
  `HAVING_REQUIRES_AGGREGATE_FIELD`.
- Preserved Python's aggregate-measure `slice` auto-lift compatibility path.
- Updated focused tests to use Java-style aggregate aliases where the test goal
  is HAVING generation or compose forwarding.
- Added a semantic-scale regression proving direct measure HAVING fails while
  `sum(salesAmountYuan) as totalSalesAmountYuan` succeeds.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_scale_factor.py tests/test_dataset_model/test_case_insensitive_field_resolve.py tests/test_dataset_model/test_auto_groupby.py tests/compose/compilation/test_per_base.py tests/test_dataset_model/test_semantic_query.py -q`
  - `174 passed in 7.41s`
- `.venv/bin/python -m pytest tests/integration/test_java_semantic_scale_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py tests/test_dataset_model/test_semantic_scale_factor.py -q`
  - `16 passed in 0.46s`
- `.venv/bin/python -m pytest -q`
  - `4069 passed, 232 skipped, 51 warnings in 18.44s`

## Notes

- This is a validation boundary change, not a SQL rendering rewrite.
- Predefined aggregate calculated fields remain supported in direct HAVING
  because they are compiled aggregate expressions, not ordinary base measures.
- Pivot member HAVING uses a separate path and was intentionally not changed in
  this pass.
