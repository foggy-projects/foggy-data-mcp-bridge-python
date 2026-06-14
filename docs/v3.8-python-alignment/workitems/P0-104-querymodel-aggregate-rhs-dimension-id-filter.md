---
doc_purpose: Track Python aggregate relation runtime evidence for RHS dimension $id fixed filters.
version: v3.8-python-alignment
priority: P0-104
status: complete
owner: python-engine
---

# P0-104 QueryModel Aggregate RHS Dimension ID Filter

Date: 2026-06-14

## Scope

P0-104 closes the next low-risk aggregate relation boundary after P0-103:
fixed filters on RHS aggregate-source dimension `$id` fields.

Covered in Python:

- RHS dimension `$id` filter lowering inside the pre-aggregate subquery,
- RHS dimension join emitted on the aggregate source alias,
- `$id` resolved to the dimension table primary key column,
- no raw `dimension$id` token leakage in generated SQL,
- coexistence with request-slice join-key pushdown,
- live SQLite result evidence.

Out of scope:

- Java-exported concrete O615 RHS dimension `$id` fixture replay,
- RHS nested dimension `$id` paths,
- request-time RHS dimension `$id` filters beyond existing safe runtime-filter
  guards,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

The Java O615 tests include dimension `$id` request/filter shapes around
`destinationServiceArea$id` and RHS dimension filter resolution. Python still
does not model the full O615 business graph in this neutral SQLite lane, so
P0-104 proves the reusable engine primitive: when a RHS aggregate filter uses a
single-hop dimension `$id`, Python resolves it through the RHS dimension join
and applies it before aggregation.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationRhsDimensionIdFilterQueryModel` uses
  `FactSalesModel.product$id = 101` as a fixed RHS filter.
- The RHS `FactSalesModel` fixture already has `product -> dim_product` with
  `product_key` as the dimension primary key.

New test:

- `test_p0_104_rhs_dimension_id_fixed_filter_joins_dimension_inside_rhs`
  verifies the generated SQL contains
  `left join dim_product dp on agg_src.product_key = dp.product_key` and
  `dp.product_key = ?`, does not leak `product$id`, pushes the request
  `orderId` slice to `agg_src.order_id = ?`, and executes against SQLite with
  the expected single-row aggregate result.

No engine code was required for this step; the existing RHS dimension filter
renderer already handled `$id` through `resolve_field_strict`.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_104 -q`

Result:

`1 passed, 46 deselected in 0.61s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`68 passed in 0.73s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `47 passed in 0.64s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated after P0-104. The immediately preceding
P0-103 full run still had only the known MySQL8 real-db timeWindow data/env
failure outside the aggregate relation surface:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.

## Remaining Boundary

Still open:

- Java fixture export/replay for the concrete O615 `destinationServiceArea$id`
  shape,
- full O615 explicit multi-join graph planning in Python,
- positive nested dimension-path lowering,
- request-time RHS dimension `$id` filter evidence if Java exports a stable
  neutral case,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
