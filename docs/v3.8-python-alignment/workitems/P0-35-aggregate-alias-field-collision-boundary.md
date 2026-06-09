# P0-35 Aggregate Alias Field Collision Boundary

Date: 2026-06-09

## Goal

Close the explicit HAVING ambiguity left after P0-33: when `request.having`
uses a selected aggregate alias, that alias must not shadow an existing model
field. Otherwise `sum(salesAmount) as salesAmount` can make a base measure look
like an eligible aggregate alias in explicit HAVING.

## Scope

- Python semantic query builder selected aggregate aliases.
- Inline aggregate columns such as `sum(salesAmount) as totalSales`.
- Explicit aliases on aggregate measures such as `salesAmount AS totalSales`.
- Case-insensitive collision detection against table model schema fields when
  explicit HAVING references the colliding alias.
- Focused regression coverage in auto-groupby/HAVING tests.
- Versioned docs and test evidence.

## Contract

- Explicit HAVING cannot reference a selected aggregate alias that collides
  with an existing schema field, ignoring case.
- `sum(salesAmount) as salesAmount` and
  `sum(salesAmount) as SalesAmount` fail closed with
  `AGGREGATE_ALIAS_COLLIDES_WITH_FIELD` when same-layer explicit HAVING
  references that alias.
- `salesAmount AS salesAmount` on an aggregate measure fails closed for the
  same reason when explicit HAVING references that alias.
- Legitimate aggregate aliases such as `totalSales` remain valid in selected
- columns and explicit HAVING.
- Aggregate output aliases that collide with schema fields remain allowed as
  projected column names when they are not used to bypass explicit HAVING
  validation; compose downstream relation naming depends on that behavior.
- HAVING comparisons between two selected aggregate aliases remain supported.

## Non-Scope

- Rewriting the formula compiler.
- Changing calculated-field post-aggregate staged computation.
- Changing pivot member `having` semantics.
- Odoo model or registry updates.
- Making alias matching case-insensitive for normal query references.

## Acceptance

- Aggregate aliases colliding with model fields fail closed when explicit
  HAVING references them.
- Collision checks are case-insensitive.
- Distinct selected aggregate aliases still compile in HAVING, including
  alias-to-alias comparisons.
- Focused Python tests pass.
