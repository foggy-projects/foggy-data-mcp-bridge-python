---
doc_purpose: Track bounded left dimension key request-slice pushdown for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-100
status: complete
owner: python-engine
---

# P0-100 QueryModel Aggregate Left Dimension Slice

Date: 2026-06-13

## Scope

P0-100 implements the next bounded dimension-path aggregate relation behavior:
a request slice on a left/root dimension key that is also an aggregate relation
join key.

This corresponds to the Java backlog item
`aggregateRelationOnLeftDimensionKeySliceShouldResolveJoinPath`, but stays
engine-neutral because the current v3 fixture does not yet export that case.

The implemented boundary is:

- request slice field may be a single-level left dimension property such as
  `store$storeId`,
- the root query materializes the needed dimension join,
- the outer predicate filters the joined dimension property,
- if the same field is mapped by aggregate relation conditions, the slice also
  pushes to the RHS grouped key,
- diagnostics record the pushed RHS `where` expression.

Nested `joinTo` dimension paths, O615 alias/no-column cases, external dialects,
and business-model fixtures remain out of scope.

## Implementation

- Reused the P0-99 root dimension join resolver for aggregate relation request
  slices.
- Threaded the root join collector through `_render_aggregate_outer_filters`.
- Kept outer SQL and RHS pushdown parameter order deterministic:
  fixed RHS relation filters, pushed RHS slice filters, then outer predicates.
- Added a focused SQLite runtime test over neutral `fact_order` and
  `dim_store` tables.

## Verification

Focused aggregate SQLite command:

`.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`

Result:

`39 passed in 0.81s`

The new test validates:

- root dimension join:
  `left join dim_store ds on t1.store_key = ds.store_key`,
- aggregate ON condition:
  `ds.store_id = storeAggByBusinessId.storeId`,
- pushed RHS filter:
  `agg_src.store_id = ?`,
- outer dimension filter:
  `ds.store_id = ?`,
- diagnostics:
  pushed `store$storeId` to RHS `where`,
- live SQLite rows for both orders attached to `STORE001`.

## Remaining Boundary

Still open:

- nested dimension paths and `joinTo` chains,
- request slices on dimension paths that are not aggregate relation join keys,
- O615 no-column / explicit alias / tenant guard regressions,
- dimension-table denied-column governance for aggregate relation dimension
  paths,
- external dialect SQL and explain evidence,
- production TMS/Odoo fixture proof.
