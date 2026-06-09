# P0-36 Formula Parity Catalog And QM Audit Refresh Progress

Date: 2026-06-09

## Completed

- Rechecked the active formula parity and compiler focused suite.
- Updated `scripts/audit_qm_formulas.py` to parse JavaScript-like multiline
  string concatenation used by Odoo QM formulas.
- Added explicit skipped classification for formulas that carry window metadata
  and are validated by the window-function query path.
- Regenerated
  `docs/v3.8-python-alignment/formula-audit-p0-36.md`.
- Added script regression tests for multiline formula extraction and window
  formula skipping.

## Evidence

Current QM audit over `src/foggy/demo`:

- QM files with formulas: 8
- Formula expressions: 17
- Compiler-compatible: 15
- Compiler-incompatible: 0
- Window-formula skipped: 2
- `filter_condition` usages: 0

Skipped window formulas:

- `RANK()` in `FactSalesQueryModel.qm`
- `AVG(salesAmount)` in `FactSalesQueryModel.qm`

## Verification

Passed:

- `.venv/bin/python scripts/audit_qm_formulas.py --root src/foggy/demo --out docs/v3.8-python-alignment/formula-audit-p0-36.md`
  - result: exit 0
- `.venv/bin/python -m pytest tests/test_scripts/test_audit_qm_formulas.py -q`
  - result: `2 passed in 0.43s`
- `.venv/bin/python -m pytest tests/integration/test_formula_parity.py tests/test_dataset_model/test_formula_compiler.py tests/test_dataset_model/test_semantic_service_formula_compiler.py tests/test_dataset_model/test_formula_compiler_capabilities.py tests/test_formula_security.py -q`
  - result: `192 passed in 0.83s`
- `.venv/bin/ruff check scripts/audit_qm_formulas.py tests/test_scripts/test_audit_qm_formulas.py`
  - result: `All checks passed!`
- `.venv/bin/python -m pytest -q`
  - result: `4075 passed, 232 skipped, 52 warnings in 17.46s`

## Notes

- The earlier P0 plan statement that current formula parity pytest fails is now
  stale for the active Python worktree. The focused formula suite is green; the
  remaining formula work is bounded to new Java snapshot cases or actual future
  compiler gaps.
