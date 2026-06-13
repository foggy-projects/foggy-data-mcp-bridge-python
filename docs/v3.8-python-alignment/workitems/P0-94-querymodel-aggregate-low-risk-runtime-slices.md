---
doc_purpose: Track low-risk Python runtime slices driven by the Java v3 aggregate relation snapshot.
version: v3.8-python-alignment
priority: P0-94
status: complete
owner: python-engine
---

# P0-94 QueryModel Aggregate Low-Risk Runtime Slices

Date: 2026-06-13

## Scope

P0-94 implements the lowest-risk runtime slices from the Java v3 aggregate
relation fixture. It stays inside the narrow SQLite aggregate relation renderer
and does not expand to Odoo models, external dialects, multi-relation planning,
or broad QueryModel stage support.

## Implementation

- Added unsafe runtime `extData` string refusal with public code
  `QUERYMODEL_AGGREGATE_JOIN_RUNTIME_FILTER_UNSAFE`.
- Kept unsafe runtime values out of generated SQL and error text.
- Added outer-only `is null` / `is not null` support for aggregate relation
  output aliases and RHS group-key outputs that are not left join keys.
- Exposed aggregate relation diagnostics in
  `debug.extra.aggregateRelationDiagnostics` for validate and execute paths.
- Extended field validation so aggregate relation `group_by` output fields are
  accepted as aggregate relation schema fields.

## Verification

- Focused runtime command:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
- Result after P0-94: `32 passed in 0.55s`.
- The same suite remains green after P0-95 as part of the combined aggregate
  run.

## Remaining Boundary

Composite keys, left/nested dimension keys, RHS dimension joins, and O615
business-shaped cases remain fixture/replay evidence unless a later work item
implements a bounded Python runtime slice.
