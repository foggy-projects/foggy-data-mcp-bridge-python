# P0-35 Aggregate Alias Field Collision Boundary Progress

Date: 2026-06-09

## Completed

- Added explicit HAVING validation for selected aggregate aliases that collide
  with model fields in `SemanticQueryService`.
- Applied the validation to inline aggregate expressions and explicit aliases
  on aggregate measures when explicit HAVING references the colliding alias.
- Made collision detection case-insensitive against the model schema field set
  and against case-normalized HAVING fields.
- Added regression coverage for inline aggregate alias collisions, case-folded
  collisions, and explicit aggregate measure alias collisions.
- Added a positive regression for HAVING comparisons between two distinct
  selected aggregate aliases.
- Preserved compose downstream relation naming where aggregate output aliases
  intentionally reuse business field names without same-layer HAVING.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_auto_groupby.py -q`
  - `25 passed in 0.46s`
- `.venv/bin/python -m pytest tests/test_dataset_model/test_auto_groupby.py tests/compose/compilation/test_derived.py::TestDerivedEdgeCases::test_derived_slice_nested_or_with_is_null tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_selects_left_non_conflicting_dollar_field tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_preserves_no_columns_derived_left_schema tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_side_and_local_qualified_refs tests/compose/compilation/test_join.py::TestJoinBasic::test_postgres_query_after_join_accepts_inherited_source_alias_refs -q`
  - `30 passed in 0.15s`
- `.venv/bin/python -m pytest tests/test_dataset_model/test_auto_groupby.py tests/test_dataset_model/test_case_insensitive_field_resolve.py tests/test_dataset_model/test_semantic_scale_factor.py tests/test_dataset_model/test_semantic_query.py tests/test_dataset_model/test_sql_quoting_and_errors.py -q`
  - `175 passed in 7.61s`
- `.venv/bin/python -m pytest -q`
  - `4073 passed, 232 skipped, 52 warnings in 17.68s`
- `.venv/bin/ruff check tests/test_dataset_model/test_auto_groupby.py`
  - `All checks passed!`

Blocked:

- Scoped ruff over
  `src/foggy/dataset_model/semantic/service.py tests/test_dataset_model/test_auto_groupby.py`
  is still blocked by existing `service.py` file-wide lint debt
  (`typing.List`/`Dict` modernization, historical unused imports, and import
  sorting). The focused test file lint is clean after this pass.
