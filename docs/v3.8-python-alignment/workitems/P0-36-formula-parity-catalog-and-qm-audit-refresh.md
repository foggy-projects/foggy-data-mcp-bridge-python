# P0-36 Formula Parity Catalog And QM Audit Refresh

Date: 2026-06-09

## Goal

Refresh the formula parity evidence after the P0-35 alias boundary fix and
separate real FormulaCompiler incompatibilities from audit-script false
positives.

## Scope

- Java formula parity catalog replay through
  `tests/integration/test_formula_parity.py`.
- Python formula compiler focused regression set.
- QM formula audit over `src/foggy/demo`.
- Audit-script parsing for JavaScript-like QM formula values.
- Window-formula classification in the audit report.

## Contract

- Concatenated string formulas such as
  `"sum(if(...)" + " && ..." + " ...)"` are parsed as one expression.
- Window formulas with `partitionBy`, `windowOrderBy`, or `windowFrame` are not
  treated as scalar/aggregate FormulaCompiler failures.
- Non-window formulas must compile through `FormulaCompiler` or be reported as
  incompatible with a non-zero audit exit.
- Deprecated `filter_condition` / `filterCondition` usage remains counted and
  must stay at zero for demo QMs.

## Non-Scope

- Changing formula compiler semantics.
- Implementing post-aggregate calculated-field staging.
- Changing window-function SQL generation.
- Refreshing Odoo generated registry models.

## Acceptance

- Formula focused pytest remains green.
- QM formula audit exits zero for `src/foggy/demo`.
- Audit report records compiler-compatible, incompatible, and skipped window
  formula counts separately.
- Script-level regression tests cover multiline formula parsing and window
  formula skipping.
