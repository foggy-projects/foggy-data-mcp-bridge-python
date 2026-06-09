# P0-33 HAVING Aggregate Alias Strictness

Date: 2026-06-09

## Goal

Close the Python/Java drift found during P0-32: explicit `request.having`
conditions over ordinary aggregate measures should use a selected aggregate
alias instead of relying on the engine to reinterpret the base measure name.

## Scope

- Python semantic query builder HAVING validation.
- Focused coverage for:
  - semantic-scale aggregate measures,
  - case-insensitive field resolution with explicit aggregate aliases,
  - auto-groupby HAVING behavior,
  - compose plan HAVING forwarding.
- Versioned docs and test evidence.

## Contract

- `request.having` accepts selected aggregate aliases, for example
  `sum(salesAmount) as totalSales` with `having totalSales > 0`.
- `request.having` rejects direct ordinary aggregate measure fields, for
  example `having salesAmount > 0`, with `HAVING_REQUIRES_AGGREGATE_FIELD`.
- Aggregate calculated fields and predefined formula aggregate fields keep their
  existing supported path.
- `slice` aggregate-measure shorthand keeps Python's compatibility behavior:
  pure aggregate slice conditions are still auto-lifted to HAVING when the
  feature flag is enabled.

## Non-Scope

- Changing pivot member `having` semantics.
- Removing aggregate-slice auto-lift compatibility.
- Token-by-token SQL parity with Java for every HAVING expression.
- Odoo model or registry updates.

## Acceptance

- Direct ordinary aggregate-measure HAVING fails closed.
- Explicit aggregate alias HAVING succeeds and preserves semantic-scale SQL.
- Existing slice auto-lift coverage continues to pass.
- Focused Python tests pass.
