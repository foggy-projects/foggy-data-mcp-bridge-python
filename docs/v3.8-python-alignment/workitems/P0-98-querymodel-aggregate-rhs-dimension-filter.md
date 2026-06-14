---
doc_purpose: Track bounded RHS dimension fixed-filter lowering for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-98
status: complete
owner: python-engine
---

# P0-98 QueryModel Aggregate RHS Dimension Filter

Date: 2026-06-13

## Scope

P0-98 implements the Java v3 aggregate relation fixture case
`aggregate-join-rhs-dimension-fixed-filter` for the Python narrow SQLite
runtime path.

The implemented boundary is intentionally small:

- RHS aggregate relation filters may reference one right-model dimension field
  such as `product$categoryId`.
- The RHS aggregate subquery materializes the corresponding
  `DimensionJoinDef` as a `left join` before applying the filter.
- Fixed RHS filters, request-slice join-key pushdown, grouping, and live SQLite
  execution keep the existing aggregate relation behavior.

This item does not implement left-side dimension join keys, nested dimension
paths, O615 no-column/tenant guard behavior, external dialects, or production
TMS/Odoo models.

## Implementation

- Added a RHS filter resolver in `SemanticQueryService` that recognizes
  strict `dimension$property/id/caption` fields carrying a `join_def`.
- Added a deduplicated RHS join collector for aggregate relation subqueries.
- Kept ordinary RHS columns, dimensions, and measures on the existing
  `_resolve_aggregate_right_field_sql(...)` path.
- Kept nested `joinTo` dimension filters fail-closed for now.
- Added an engine-neutral SQLite model with `fact_sales.product_key` joined to
  `dim_product.product_key`.

## Verification

Focused aggregate SQLite command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`

Result:

`37 passed in 0.78s`

The new test validates:

- Java v3 fixture case id:
  `aggregate-join-rhs-dimension-fixed-filter`.
- RHS subquery marker:
  `from fact_sales agg_src left join dim_product`.
- RHS dimension predicate marker:
  `dp.category_id = ?`.
- Forbidden marker:
  `agg_src.category_id`.
- Java params:
  `["COMPLETED", "CAT001", "ORD20240101000001", "ORD20240101000001"]`.
- Live SQLite result row:
  `{"orderId": "ORD20240101000001", "amount": 10998.0, "salesAmount": 9898.2}`.

## Remaining Boundary

P0-98 does not claim full dimension-path aggregate relation parity.

Still open:

- left joined dimension keys in the outer query,
- nested dimension paths and `joinTo` chains,
- dimension-field governance over denied dimension-table columns,
- no-column / alias / tenant-guard O615 regressions,
- external dialect SQL and explain evidence,
- production TMS/Odoo fixtures.

Those should remain fixture-led follow-up work, with engine-neutral SQLite
proofs before business-model expansion.
