---
doc_purpose: Track Python aggregate relation fail-closed evidence for nested dimension $id filters.
version: v3.8-python-alignment
priority: P0-107
status: complete
owner: python-engine
---

# P0-107 QueryModel Aggregate Nested Dimension ID Fail-Closed

Date: 2026-06-14

## Scope

P0-107 extends the P0-101 nested dimension fail-closed boundary to RHS nested
dimension `$id` filters. Python still defers positive nested `joinTo` path
lowering, so nested dimension IDs must remain fail-closed before SQL generation.

Covered in Python:

- RHS aggregate relation fixed filters on nested dimension `$id` fields,
- public validate-mode refusal before SQL generation,
- deterministic `AGGREGATE_JOIN_UNSUPPORTED` response,
- no nested dimension field token or physical nested table leakage in the
  refusal message.

Out of scope:

- positive nested dimension SQL lowering,
- nested dimension runtime filters,
- left/root nested dimension `$id` ON keys or request slices,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate relation coverage includes dimension-path keys and filters, while
Python P0-101 deliberately kept nested `joinTo` paths fail-closed until stable
fixture-backed lowering exists. P0-107 adds the missing `$id` variant to that
same boundary rather than opening positive nested path support.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationNestedRhsDimensionIdFilterQueryModel` uses the
  RHS nested dimension filter `category$id = 10`.
- The RHS model reuses `category -> product` as a nested `joinTo` dimension.

New test:

- `test_p0_107_rhs_nested_dimension_id_filter_fails_closed` verifies validate
  mode returns `AGGREGATE_JOIN_UNSUPPORTED`, includes the existing
  "nested RHS dimension filters are not supported" marker, and does not leak
  `category$id` or `dim_category`.

No engine code was required for this step; the existing nested RHS dimension
guard already covers `$id` once exercised.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_107 -q`

Result:

`1 passed, 50 deselected in 0.64s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`72 passed in 0.73s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `51 passed in 0.66s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated after P0-107. The latest full baseline from
P0-103 still had only the known MySQL8 real-db timeWindow data/env failure
outside the aggregate relation surface:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.

## Remaining Boundary

Still open:

- positive nested dimension SQL lowering,
- nested dimension runtime filter fail-closed evidence,
- left/root nested dimension `$id` ON-key and request-slice fail-closed
  evidence,
- Java fixture export/replay for accepted nested dimension behavior,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
