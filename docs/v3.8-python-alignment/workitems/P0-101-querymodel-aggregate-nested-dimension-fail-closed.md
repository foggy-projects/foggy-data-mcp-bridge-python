---
doc_purpose: Track nested dimension path fail-closed boundaries for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-101
status: complete
owner: python-engine
---

# P0-101 QueryModel Aggregate Nested Dimension Fail-Closed

Date: 2026-06-13

## Scope

P0-101 locks the current Python boundary for aggregate relation dimension
paths that require a nested `joinTo` chain.

Java acceptance has evidence for nested left dimension path resolution, but the
current Python runtime should not infer multi-hop lowering from the single-hop
P0-98 through P0-100 slices. Until Java exports a stable nested-path fixture
and Python has a dedicated lowering design, nested paths must fail closed.

Covered entry points:

- RHS aggregate relation fixed filters on nested dimension properties,
- left/root aggregate relation ON keys on nested dimension properties,
- request slices on left/root nested dimension properties.

Out of scope:

- positive nested dimension SQL lowering,
- non-join-key dimension-path pushdown,
- O615 no-column / explicit alias / tenant guard behavior,
- external dialect SQL,
- Odoo/TMS business-model fixture expansion.

## Implementation

No broad SQL lowering was added in this item.

The existing aggregate relation resolvers already reject nested joins:

- `_resolve_aggregate_right_filter_field_sql(...)` rejects RHS `joinTo`
  dimension filters,
- `_resolve_aggregate_root_join_field_sql(...)` rejects root `joinTo`
  dimension join keys and request-slice fields.

P0-101 adds focused validate-mode tests proving those branches are reachable
from the aggregate relation API surface and return
`AGGREGATE_JOIN_UNSUPPORTED` without generating SQL.

## Verification

Focused new-test command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -k p0_101 -q`

Result:

`3 passed, 39 deselected in 0.75s`

The new tests cover:

- RHS nested dimension filter `category$segment`,
- left nested dimension ON key `region$regionId`,
- left nested dimension request slice `region$regionId`.

Each test asserts:

- `response.sql is None`,
- `AGGREGATE_JOIN_UNSUPPORTED` is present,
- `error_detail.code == AGGREGATE_JOIN_UNSUPPORTED`,
- nested physical table names such as `dim_category` and `dim_region` are not
  leaked in the public error.

## Remaining Boundary

Still open:

- Java nested-path fixture export and replay,
- positive multi-hop dimension join lowering,
- deterministic aliasing and parameter order for nested RHS/root joins,
- denied-column governance across dimension tables,
- external dialect SQL shape and explain evidence,
- production TMS/Odoo proof.
