---
doc_purpose: Track Python aggregate relation fail-closed evidence for nested dimension runtime filters.
version: v3.8-python-alignment
priority: P0-109
status: complete
owner: python-engine
---

# P0-109 QueryModel Aggregate Nested Dimension Runtime Fail-Closed

Date: 2026-06-14

## Scope

P0-109 extends the nested dimension fail-closed boundary to runtime filters.
Python still defers positive nested `joinTo` path lowering, so nested dimension
runtime filters must fail closed before SQL generation even when the runtime
value is available in request context.

Covered in Python:

- RHS nested dimension `$id` runtime filters,
- runtime value supplied through `context.attributes.extData`,
- public validate-mode refusal before SQL generation,
- deterministic `AGGREGATE_JOIN_UNSUPPORTED` response,
- no nested dimension field token, runtime key, or physical nested table leakage
  in refusal messages.

Out of scope:

- positive nested dimension SQL lowering,
- left/root nested dimension runtime filters,
- broader runtime object-value policy beyond the existing aggregate runtime
  filter guard,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate relation coverage includes dimension-path filters and runtime RHS
filter behavior. Python now supports single-hop RHS dimension `$id` runtime
filters through P0-105, but nested `joinTo` dimension paths remain deliberately
closed. P0-109 proves the runtime variant follows the nested-path guard instead
of attempting partial lowering.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationNestedRhsDimensionIdRuntimeFilterQueryModel` uses
  `category$id = {extData: categoryKey}` as a RHS aggregate filter.
- The RHS model reuses `category -> product` as a nested `joinTo` dimension.

New test:

- `test_p0_109_rhs_nested_dimension_id_runtime_filter_fails_closed` supplies
  `context.attributes.extData.categoryKey = 10` and verifies validate mode
  returns `AGGREGATE_JOIN_UNSUPPORTED`, includes the existing nested RHS
  dimension marker, and does not leak `category$id`, `categoryKey`, or
  `dim_category`.

No engine code was required for this step; the existing nested RHS dimension
guard takes precedence before SQL generation.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_109 -q`

Result:

`1 passed, 53 deselected in 0.64s`

Aggregate SQLite alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`

Result:

`54 passed in 1.09s`

Aggregate parity combo command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`75 passed in 1.24s`

Static checks:

- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated in this step. Latest full-suite baseline
remains P0-103: `1 failed, 4242 passed, 168 skipped`, with the known unrelated
MySQL8 real-DB timeWindow matrix failure.

## Remaining Boundary

Still open:

- positive nested dimension SQL lowering,
- left/root nested dimension runtime filter evidence,
- Java fixture export/replay for accepted nested dimension behavior,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
