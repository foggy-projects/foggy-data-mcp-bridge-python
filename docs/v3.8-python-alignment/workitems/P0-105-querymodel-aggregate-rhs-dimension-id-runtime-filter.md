---
doc_purpose: Track Python aggregate relation runtime evidence for RHS dimension $id runtime filters.
version: v3.8-python-alignment
priority: P0-105
status: complete
owner: python-engine
---

# P0-105 QueryModel Aggregate RHS Dimension ID Runtime Filter

Date: 2026-06-14

## Scope

P0-105 extends P0-104 from fixed RHS dimension `$id` filters to runtime filters
resolved from request context.

Covered in Python:

- RHS dimension `$id` runtime filter lowering inside the pre-aggregate subquery,
- runtime value resolution from `context.attributes.extData`,
- RHS dimension join emitted on the aggregate source alias,
- `$id` resolved to the dimension table primary key column,
- no raw `dimension$id` or `ctx.extData` token leakage in generated SQL,
- coexistence with request-slice join-key pushdown diagnostics,
- missing runtime value fail-closed behavior,
- unsafe runtime string fail-closed behavior without physical table leakage,
- live SQLite result evidence.

Out of scope:

- Java-exported concrete O615 RHS dimension `$id` runtime fixture replay,
- RHS nested dimension `$id` runtime filters,
- arbitrary runtime object values beyond the existing aggregate runtime filter
  guard,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate relation coverage includes runtime RHS filter and dimension-path
filter shapes, while O615 includes concrete dimension `$id` join-path cases.
Python does not yet model the full O615 graph in the neutral SQLite lane, so
P0-105 proves the lower-level reusable behavior: a RHS single-hop dimension
`$id` runtime filter resolves through the RHS dimension join before aggregation
and preserves the existing runtime-value fail-closed contract.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationRhsDimensionIdRuntimeFilterQueryModel` uses
  `FactSalesModel.product$id = {extData: productKey}` as a RHS aggregate fixed
  filter with runtime value binding.
- The RHS fixture reuses `FactSalesModel.product -> dim_product`, where
  `product_key` is the dimension primary key.

New tests:

- `test_p0_105_rhs_dimension_id_runtime_filter_resolves_inside_rhs`
  validates and executes a query with `context.attributes.extData.productKey =
  101`, asserting `dp.product_key = ?`, no raw `product$id` or `ctx.extData`
  leakage, pushed `orderId` diagnostics, and the expected SQLite result.
- `test_p0_105_rhs_dimension_id_runtime_filter_fails_closed` verifies missing
  runtime value and unsafe string values fail closed without leaking
  `fact_sales` or `dim_product` in the error.

No engine code was required for this step; the existing aggregate runtime
filter resolver and RHS dimension field resolver already compose correctly.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_105 -q`

Result:

`2 passed, 47 deselected in 0.62s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`70 passed in 0.75s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `49 passed in 0.69s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated after P0-105. The latest full baseline from
P0-103 still had only the known MySQL8 real-db timeWindow data/env failure
outside the aggregate relation surface:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.

## Remaining Boundary

Still open:

- Java fixture export/replay for concrete O615 `destinationServiceArea$id`
  request/runtime cases,
- full O615 explicit multi-join graph planning in Python,
- positive nested dimension-path lowering,
- RHS nested dimension `$id` runtime filters,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
