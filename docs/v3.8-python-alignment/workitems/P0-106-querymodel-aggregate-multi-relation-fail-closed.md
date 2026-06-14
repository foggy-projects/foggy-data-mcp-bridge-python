---
doc_purpose: Track Python aggregate relation fail-closed evidence for multi-relation models.
version: v3.8-python-alignment
priority: P0-106
status: complete
owner: python-engine
---

# P0-106 QueryModel Aggregate Multi-Relation Fail-Closed

Date: 2026-06-14

## Scope

P0-106 locks the current Python boundary for QueryModel models that carry more
than one aggregate relation. Python still supports only one aggregate relation
in the narrow SQLite runtime path, so multi-relation models must fail closed
before SQL generation.

Covered in Python:

- multi aggregate-relation carrier count detection,
- public `query_model(..., mode="validate")` refusal before SQL generation,
- `build_query_with_governance(...)` refusal before SQL generation,
- deterministic `AGGREGATE_JOIN_UNSUPPORTED` error detail with
  `carrierCount=2`,
- no physical root/RHS table leakage in refusal messages.

Out of scope:

- positive multi-relation SQL planning,
- aggregate output alias collision resolution across relations,
- multi-relation public metadata composition,
- external SQL dialects,
- production TMS/Odoo database evidence.

## Java Evidence Read

Java aggregate join support continues to expand, but the Python P0 SQLite path
has intentionally stayed narrow and single-relation. Earlier workitems list
multi-relation planning as a remaining broad implementation gap. P0-106 keeps
that gap explicit and fail-closed instead of allowing Python to silently choose
the first relation.

## Implementation

New neutral model:

- `OrderSalesAggregateRelationMultiRelationQueryModel` carries two aggregate
  relations against `FactSalesModel`: `fsByOrder` and `fsCostByOrder`.

New test:

- `test_p0_106_multi_relation_model_fails_closed_before_sql` verifies both the
  public validate path and `build_query_with_governance(...)` reject the model
  with `AGGREGATE_JOIN_UNSUPPORTED`, include `carrier_count=2`, expose
  structured `carrierCount: 2` error detail on the public response, and do not
  leak `fact_order` or `fact_sales`.

No engine code was required for this step; the existing single-relation guard
already refuses the broader shape.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_106 -q`

Result:

`1 passed, 49 deselected in 0.64s`

Aggregate alignment command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`

Result:

`71 passed in 0.76s`

Additional checks:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  passed with `50 passed in 0.66s`.
- `.venv/bin/python -m ruff check tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py --select F`
  passed.
- `git diff --check` passed.

Full Python pytest was not repeated after P0-106. The latest full baseline from
P0-103 still had only the known MySQL8 real-db timeWindow data/env failure
outside the aggregate relation surface:
`tests/integration/test_time_window_real_db_matrix.py::test_real_db_comparative_windows_execute[mysql8-yoy-month-columns0-group_by0-3]`.

## Remaining Boundary

Still open:

- positive multi-relation SQL planning,
- aggregate output alias collision and metadata collision policy,
- Java fixture export/replay for stable multi-relation behavior if accepted,
- MySQL/PostgreSQL aggregate relation dialect evidence,
- production TMS/Odoo evidence.
