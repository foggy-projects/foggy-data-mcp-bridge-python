---
doc_purpose: Track structured accessBuilder field-ref pushdown for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-96
status: complete
owner: python-engine
---

# P0-96 QueryModel Aggregate Structured Access Pushdown

Date: 2026-06-13

## Scope

P0-96 implements the lowest-risk replay-only v3 aggregate relation case left
after P0-95:

- Java fixture case:
  `aggregate-join-structured-access-builder-pushdown`.
- Python runtime model:
  `OrderSalesAggregateRelationAccessQueryModel`.
- Supported shape:
  a structured `RowFilterType.EXPRESSION` row filter that compiles to a single
  aggregate relation join-key equality such as `orderId == "ORD..."`.

The outer access filter remains the security boundary. The pushdown is only an
extra RHS `where` predicate for SQL/result parity and performance shape.

## Implementation

- Replaced the aggregate relation access-rendering call with a structured
  helper that returns:
  - outer access SQL and params,
  - optional RHS pushed `where` SQL and params,
  - optional pushdown diagnostics.
- Raw SQL accessBuilder predicates remain outer-only and keep full RHS
  projection behavior.
- Structured expression access filters are pushed only when all of the
  following are true:
  - row filter type is `expression`,
  - the compiled expression references exactly one field,
  - the expression has exactly one bind parameter,
  - the referenced field is a left join key mapped to an RHS group key,
  - the compiled SQL shape is a simple equality between that left key and a
    parameter.
- Unsupported structured access shapes keep the old outer-only behavior.

## Verification

- Focused aggregate SQLite command:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
- Result: `35 passed in 0.90s`.

The new test validates the Java fixture's structured access case with live
SQLite execution:

- RHS subquery includes `agg_src.order_id = ?`.
- Outer query still includes `t1.order_id = ?`.
- Params match Java: `["COMPLETED", "ORD20240101000001", "ORD20240101000001"]`.
- Diagnostics match Java's pushed `where` entry for `orderId`.
- Response rows match the Java snapshot.

## Remaining Boundary

P0-96 does not implement:

- left or RHS dimension-path runtime lowering,
- O615 alias/no-column/tenant guard behavior,
- external dialect SQL/explain evidence,
- multi-relation aggregate planning,
- `groupBy`, `having`, post stages, `timeWindow`, or pivot combinations.

Those remain follow-up items behind fixture-driven gates.
