---
doc_purpose: Track the first Python runtime boundary for O615-shaped aggregate relation no-column, alias, and tenant guard cases.
version: v3.8-python-alignment
priority: P0-102
status: complete
owner: python-engine
---

# P0-102 QueryModel Aggregate O615 Boundary

Date: 2026-06-14

## Scope

P0-102 starts the O615-shaped aggregate relation follow-up from the Java
acceptance evidence, but keeps the Python work engine-neutral and bounded to
the narrow SQLite aggregate relation runtime path.

Covered in Python:

- no-columns request payloads using the model default projection,
- left request alias used as an aggregate relation join key,
- scalar tenant join key carried by `system_slice`,
- RHS pre-aggregate tenant guard pushdown,
- retained outer tenant guard predicate,
- user `fieldAccess` bypass for the system guard,
- no tenant guard field leakage in response columns or rows.

Out of scope:

- full O615 business models,
- explicit multi-join O615 graph planning,
- RHS dimension `$id` O615 request slices,
- positive nested dimension path lowering,
- external SQL dialects,
- production TMS/Odoo database evidence.

Those remain fixture-led follow-ups. This item only proves the lowest-risk
engine behaviors that can be represented by the existing neutral SQLite model
set.

## Java Evidence Read

The Java source tests reviewed for this item were in
`AggregateJoinQueryModelTest`:

- `aggregateRelationO615ProbeNoColumnsWithAccessShouldResolveJoinPath`,
- `aggregateRelationO615ProbeExpressJoinNoColumnsShouldResolveJoinPath`,
- `aggregateRelationO615TenantGuardShouldBypassFieldAccessWithoutLeaking`,
- `aggregateRelationO615ProbeExpressJoinDimensionIdSliceShouldResolveJoinPath`,
- `aggregateRelationO615ProbeRhsDimensionFilterShouldResolveJoinPath`.

The Java behavior relevant to this bounded Python slice is:

- no `columns` request still resolves a default aggregate relation projection,
- an external alias such as `orderNo` can be used to resolve the aggregate join
  path,
- tenant guard filters are copied into the RHS aggregate pre-filter when the
  tenant field is also an aggregate join key,
- the RHS `groupBy` retains the tenant key,
- the guard may come from system context instead of user-visible fields,
- the tenant guard does not leak into returned rows.

## Implementation

Python test fixture changes:

- `fact_order` and `fact_sales` SQLite fixtures now include a neutral
  `tenant_id` column.
- Existing rows use `TENANT_A` for `ORDER_1` and `TENANT_B` for `ORDER_2`;
  existing aggregate tests keep their prior business assertions because the
  new column is unused unless a test selects or filters it.
- `_tenant_right_model()` adds the RHS `tenantId` field.
- `_tenant_guard_model()` adds a two-key aggregate relation
  `orderId + tenantId` against `FactSalesModel`.

New tests:

- `test_p0_102_alias_key_no_columns_request_defaults_and_pushes_rhs_key`
  proves `columns=[]` defaults to the model fields plus aggregate outputs and
  still pushes an aliased join key slice to `agg_src.order_id`.
- `test_p0_102_tenant_system_slice_pushes_rhs_without_leaking_guard` proves
  `system_slice tenantId = TENANT_A` pushes `agg_src.tenant_id = ?`, keeps the
  outer `t1.tenant_id = ?` guard, keeps `tenantId` in RHS `group by`, bypasses
  user `fieldAccess`, and returns rows without `tenantId`.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_102 -q`

Result:

`2 passed, 42 deselected in 0.59s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`65 passed in 0.70s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `44 passed in 0.62s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest baseline:

`.venv/bin/python -m pytest -q`

Result:

`1 failed, 4240 passed, 168 skipped, 53 warnings in 23.44s`

The failure is the pre-existing MySQL8 real-db timeWindow matrix case
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.
The assertion found zero rows with `salesAmount__prior`, while the test expects
at least three. This is outside the aggregate relation P0-102 surface.

## Remaining Boundary

Still open:

- Java fixture export for O615 no-column / explicit join alias / tenant guard
  as a stable snapshot contract,
- RHS dimension `$id` O615 request-slice replay,
- O615 explicit multi-join graph planning in Python,
- positive nested dimension path lowering,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
