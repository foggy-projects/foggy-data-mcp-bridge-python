---
doc_purpose: Track bounded left dimension key lowering for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-99
status: complete
owner: python-engine
---

# P0-99 QueryModel Aggregate Left Dimension Key

Date: 2026-06-13

## Scope

P0-99 implements the Java v3 aggregate relation fixture case
`aggregate-join-left-dimension-key` for the Python narrow SQLite runtime path.

The implemented boundary is:

- aggregate relation `conditions[].leftField` may reference a left/root
  dimension property such as `store$storeId`,
- the root query materializes the required `DimensionJoinDef` before joining
  the RHS aggregate subquery,
- the aggregate join `on` clause compares the joined dimension property to the
  RHS grouped key,
- ordinary root request slices still stay outer-only, with Java-aligned
  `NO_JOIN_KEY_MAPPING` diagnostics when they are not relation join keys.

This item does not implement nested dimension paths, request-slice pushdown for
left dimension paths, O615 no-column/alias/tenant cases, external dialects, or
production TMS/Odoo models.

## Implementation

- Added a root dimension join resolver for aggregate relation ON conditions.
- Added deduplicated root join collection before the aggregate relation join.
- Kept nested `joinTo` dimension keys fail-closed.
- Added a neutral SQLite model:
  - `fact_order.store_key -> dim_store.store_key`,
  - relation left key `store$storeId`,
  - RHS grouped key `storeId`,
  - aggregate output `areaSqm`.
- Added Java-aligned retained diagnostic for non-join-key root slices.

## Verification

Focused aggregate SQLite command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`

Result:

`38 passed in 0.74s`

The new test validates:

- Java v3 fixture case id:
  `aggregate-join-left-dimension-key`.
- Root dimension join marker:
  `left join dim_store ds on t1.store_key = ds.store_key`.
- Aggregate ON marker:
  `ds.store_id = storeAggByBusinessId.storeId`.
- Java params:
  `["ACTIVE", "ORD20240101000001"]`.
- Java diagnostics:
  `NO_JOIN_KEY_MAPPING` for the outer-only `orderId` slice.
- Live SQLite result row:
  `{"orderId": "ORD20240101000001", "amount": 10998.0, "areaSqm": 350.0}`.

## Remaining Boundary

Still open:

- nested dimension paths and `joinTo` chains,
- request-slice pushdown for left dimension path predicates,
- O615 no-column / explicit alias / tenant guard regressions,
- dimension-table denied-column governance for aggregate relation dimension
  paths,
- external dialect SQL and explain evidence,
- production TMS/Odoo fixture proof.

Those remain fixture-led follow-up work.
