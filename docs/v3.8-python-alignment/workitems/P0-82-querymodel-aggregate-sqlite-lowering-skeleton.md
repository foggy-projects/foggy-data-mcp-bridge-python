---
doc_purpose: Track the first SQLite SQL lowering skeleton for QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-82
status: completed
owner: python-engine
---

# P0-82 QueryModel Aggregate SQLite Lowering Skeleton

Date: 2026-06-12

## Background

P0-81 defined the minimal SQL shape for Java 9.2 QueryModel aggregate join
alignment. P0-82 implements the first Python lowering path for that shape while
keeping unsupported aggregate relation variants fail-closed.

The contract source remains:

- `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
- Java cases `aggregate-join-sql-shape-sqlite` and
  `aggregate-join-fixed-rhs-filter`

## Target Outcome

- Build one-root / one-aggregate-relation SQLite SQL with RHS preaggregation.
- Render the RHS as a grouped subquery with source alias `agg_src`.
- Project aggregate relation outputs from the relation alias, not the root
  model alias.
- Preserve fixed RHS filter params in Java fixture order.
- Fail closed when RHS `groupBy` does not include every right join key.

## Implementation

- Added narrow aggregate relation lowering in
  `src/foggy/dataset_model/semantic/service.py`.
- Added aggregate-specific refusal codes in
  `src/foggy/dataset_model/aggregate_join.py`.
- Extended schema validation so aggregate relation measure aliases are treated
  as valid selectable fields.
- Updated guarded loader aggregate relation tests now that the guarded carrier
  can lower through the narrow SQLite path when the fixture shape is supported.
- Added focused P0-82 tests in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.

## Acceptance Criteria

- Completed. SQL contains the Java fixture RHS grouped subquery markers.
- Completed. SQL contains fixed RHS filters such as
  `agg_src.order_status = ?`.
- Completed. SQL contains `sum(...)`, `count(*)`, and
  `count(distinct ...)` aggregate relation outputs as applicable.
- Completed. Forbidden semantic-field markers such as `.salesAmount` do not
  appear in generated SQL.
- Completed. Missing right join key groupBy fails closed with
  `QUERYMODEL_AGGREGATE_JOIN_GROUPBY_MISSING_RIGHT_KEY`.

## Progress Tracking

- Development: completed.
- Testing: completed with focused pytest listed below.
- Experience: N/A; this is backend engine SQL generation with no UI surface.

## Verification

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`15 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
  (`68 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`10 passed`)

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/aggregate_join.py`
  - `src/foggy/dataset_model/semantic/field_validator.py`
  - `src/foggy/dataset_model/semantic/service.py`
  - `tests/test_dataset_model/test_loader_fsscript.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py`
  - `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
- Self-check:
  - The path remains limited to one aggregate relation and LEFT join.
  - Unsupported QueryModel stages still fail closed.
  - Ordinary explicit join lowering is not reused or mutated.
  - Odoo and generated registry models remain untouched.

## Remaining Risks

- SQLite is the only active SQL lowering target in this item.
- MySQL, PostgreSQL, and production TMS DB evidence remain follow-up work.
- Broader optimizer and complex QueryModel stage support remain out of scope.
