# P0-30 Semantic Scale Factor / Money Units

Date: 2026-06-08

## Goal

Align Python's core semantic query path with Java `semanticScaleFactor` for
money/unit fields so model authors can store physical minor units while users
query semantic units.

## Scope

- Semantic scale SQL helper:
  `src/foggy/dataset_model/impl/semantic_scale.py`
- TM field carriers and validation:
  `src/foggy/dataset_model/definitions/base.py`
  `src/foggy/dataset_model/impl/model/__init__.py`
  `src/foggy/dataset_model/impl/loader/__init__.py`
- Query and metadata integration:
  `src/foggy/dataset_model/semantic/service.py`
- Focused regression coverage:
  `tests/test_dataset_model/test_semantic_scale_factor.py`

## Contract

- `semanticScaleFactor` must be numeric and greater than zero.
- When scale is configured, `column` must remain a physical column name, not a
  SQL expression.
- `formulaDef` / `dialectFormulaDef` may supply SQL and then the formula result
  is scaled.
- Query SQL uses semantic units for selected properties, selected measures,
  filters, having clauses, and calculated fields.
- Metadata exposes `semanticScaleFactor`, `semanticUnit`, and
  `semanticUnitLabel`.

## Explicit Non-Scope

- Namespace-level opt-out config parity with Java.
- Cross-language neutral snapshot fixture export.
- Live DB result parity for every dialect.
- Domain-specific currency or accounting semantics.

## Acceptance

- Focused pytest coverage passes.
- Loader/model validation rejects SQL expression columns when scaled.
- V3 metadata includes scale/unit fields for fact properties, dimension
  properties, and measures.
- Formula-backed properties and measures support scale.
