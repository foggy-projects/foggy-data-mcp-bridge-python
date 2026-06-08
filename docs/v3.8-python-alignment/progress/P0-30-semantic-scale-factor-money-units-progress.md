# P0-30 Semantic Scale Factor / Money Units Progress

Date: 2026-06-08

## Completed

- Added Python semantic scale SQL helper with Java-aligned literal formatting
  and fail-closed physical-column validation.
- Added `semanticScaleFactor`, `semanticUnit`, and `semanticUnitLabel` carriers
  to fact properties, dimension properties, and measures.
- Added `formulaDef.value` / `dialectFormulaDef.value` resolution for scaled
  formula-backed properties and measures.
- Integrated scaled SQL into `resolve_field` / `resolve_field_strict` so select,
  filter, having, inline aggregate, and calculated-field references share the
  same semantic unit expression.
- Added V3 metadata exposure for scale/unit fields.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_scale_factor.py -q`
  - `8 passed in 0.48s`
- `.venv/bin/python -m pytest tests/test_dataset_model/test_semantic_scale_factor.py tests/test_dataset_model/test_semantic_service_formula_compiler.py tests/test_dataset_model/test_inline_expression.py tests/test_dataset_model/test_dictionary_discovery_metadata.py tests/test_dataset_model/test_loader_fsscript.py tests/test_dataset_model/test_semantic_query.py -q`
  - `210 passed in 8.74s`
- `.venv/bin/python -m pytest -q`
  - `4063 passed, 232 skipped, 51 warnings in 17.47s`
- `git diff --check`
  - passed

Pending:

- Optional Java/Python neutral snapshot export if semantic scale is promoted
  into the shared snapshot catalog.

## Notes

- Python keeps its existing aggregate-slice behavior: aggregate measure filters
  are lifted to HAVING when applicable. The scale expression is applied before
  aggregation, matching the Java semantic unit intent.
- Namespace-level Java opt-out remains out of this P0-30 scope.
