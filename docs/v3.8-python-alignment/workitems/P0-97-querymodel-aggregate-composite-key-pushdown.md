---
doc_purpose: Track composite-key aggregate relation pushdown proof for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-97
status: complete
owner: python-engine
---

# P0-97 QueryModel Aggregate Composite-Key Pushdown

Date: 2026-06-13

## Scope

P0-97 proves the Java v3 aggregate relation fixture case
`aggregate-join-composite-key-pushdown` against the Python narrow SQLite
runtime path.

The implemented boundary is engine-neutral:

- left model has two scalar join keys,
- RHS aggregate subquery groups by both mapped keys,
- request slices on both left keys are pushed into RHS `where`,
- aggregate output slice is pushed into RHS `having` and retained on the
  outer relation alias,
- live SQLite execution returns the Java fixture's expected empty result.

No Odoo, TMS production model, external dialect, or dimension path behavior is
implemented by this item.

## Implementation

- Added a composite-key neutral Python test model:
  `TmsStyleOrderStoreSalesAggregateRelationQueryModel`.
- Added a composite RHS field carrier for `FactSalesModel.storeKey`.
- Extended the aggregate SQLite seed with neutral `store_key` and
  `total_quantity` columns.
- Reused the existing aggregate relation renderer:
  - multiple join conditions are already rendered in the outer `on` clause,
  - multiple RHS group keys are already selected and grouped,
  - request-slice pushdown already walks each left join key independently.

## Verification

- Focused aggregate SQLite command:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
- Result: `36 passed in 1.05s`.

The new test validates:

- RHS `where` markers: `agg_src.order_id = ?`, `agg_src.store_key = ?`.
- RHS `having` marker: `having sum(agg_src.sales_amount) > ?`.
- Outer join markers for both key pairs.
- Java params:
  `["COMPLETED", "ORD20240101000001", 1, 0, "ORD20240101000001", 1, 0.0]`.
- Java diagnostics for pushed `orderId`, pushed `store$id`, and pushed
  `salesAmount`.
- Live SQLite result rows: `[]`.

## Remaining Boundary

P0-97 does not implement:

- left or RHS dimension-path runtime lowering,
- O615 alias/no-column/tenant guard behavior,
- external dialect SQL/explain evidence,
- multi-relation aggregate planning,
- `groupBy`, `having`, post stages, `timeWindow`, or pivot combinations.

Those remain follow-up items behind fixture-driven gates.
