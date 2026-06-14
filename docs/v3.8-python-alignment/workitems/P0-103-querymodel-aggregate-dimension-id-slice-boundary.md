---
doc_purpose: Track Python aggregate relation runtime evidence for non-join-key dimension request slices and dimension $id slices.
version: v3.8-python-alignment
priority: P0-103
status: complete
owner: python-engine
---

# P0-103 QueryModel Aggregate Dimension ID Slice Boundary

Date: 2026-06-14

## Scope

P0-103 continues the O615-shaped aggregate relation boundary review from
P0-102, focused on request slices that reference left-side dimension paths
which are not aggregate relation join keys.

Covered in Python:

- root dimension property request slice retained on the outer query,
- root dimension `$id` request slice retained on the outer query,
- root dimension join emitted before the aggregate relation join,
- no RHS pre-aggregate pushdown when no left-to-right join-key mapping exists,
- no raw `dimension$property` / `dimension$id` token leakage into generated SQL,
- deterministic `NO_JOIN_KEY_MAPPING` diagnostics for the retained boundary,
- live SQLite result evidence for both property and `$id` slices.

Out of scope:

- positive nested dimension-path lowering,
- multi-hop O615 explicit join graph planning,
- RHS dimension `$id` filters on the aggregate source,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

The immediate Java driver remains the O615 test family in
`AggregateJoinQueryModelTest`, especially:

- `aggregateRelationO615ProbeExpressJoinDimensionIdSliceShouldResolveJoinPath`,
- `aggregateRelationO615ProbeRhsDimensionFilterShouldResolveJoinPath`,
- the P0-102 no-column, alias-key, and tenant-guard neighbors.

Java can resolve O615 request slices such as `destinationServiceArea$id` through
the explicit join graph. Python does not yet model that full O615 business graph
in this neutral fixture lane, so P0-103 records the lower-level engine boundary:
dimension-path slices that are not aggregate join keys must stay on reachable
outer aliases and must not be copied into the RHS pre-aggregate query.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationDimensionSliceNonKeyQueryModel` uses
  `fact_order -> dim_store` as a root dimension join.
- Its aggregate relation still joins `FactSalesModel` only by `orderId`.
- Therefore `store$storeId` and `store$id` are valid root fields but have no
  left-to-right aggregate join-key mapping.

New tests:

- `test_p0_103_non_join_dimension_property_slice_stays_outer_only`
  verifies `store$storeId = STORE001` renders `ds.store_id = ?`, does not render
  `agg_src.store_id = ?`, records `NO_JOIN_KEY_MAPPING`, and executes against
  SQLite.
- `test_p0_103_non_join_dimension_id_slice_stays_outer_only`
  verifies `store$id = 1` renders `ds.store_key = ?`, does not render
  `agg_src.store_key = ?`, records `NO_JOIN_KEY_MAPPING`, and executes against
  SQLite.

No engine code was required for this step; the existing aggregate relation
lowering already retained the correct fail-safe boundary.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_103 -q`

Result:

`2 passed, 44 deselected in 0.75s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`67 passed in 0.71s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `46 passed in 0.64s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest baseline:

`.venv/bin/python -m pytest -q`

Result:

`1 failed, 4242 passed, 168 skipped, 53 warnings in 23.46s`

The failure is the same pre-existing MySQL8 real-db timeWindow matrix case
recorded in P0-102:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.
The assertion found zero rows with `salesAmount__prior`, while the test expects
at least three. This is outside the aggregate relation P0-103 surface.

## Remaining Boundary

Still open:

- Java fixture export for the concrete O615 `destinationServiceArea$id`
  request-slice case,
- full O615 explicit multi-join graph planning in Python,
- positive nested dimension-path lowering,
- RHS dimension `$id` fixed/runtime filter replay when exported as neutral
  fixtures,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
