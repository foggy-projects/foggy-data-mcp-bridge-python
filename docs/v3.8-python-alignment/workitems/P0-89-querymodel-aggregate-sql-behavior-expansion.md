---
doc_purpose: Track SQL behavior expansion for QueryModel aggregate relation alignment after P0-88.
version: v3.8-python-alignment
priority: P0-89
status: complete
owner: python-engine
---

# P0-89 QueryModel Aggregate SQL Behavior Expansion

Date: 2026-06-13

## Scope

P0-89 owns the next QueryModel aggregate relation SQL behavior expansion after
the P0-87 governance slice and the P0-88 public metadata contract. It remains
inside the Python engine to Java engine alignment line:

- engine-neutral SQLite fixtures and Java snapshot/replay evidence first;
- fail-closed behavior before broad runtime exposure;
- no Odoo business model expansion;
- no registry-generated model refresh;
- no external dialect implementation without a stable SQL/result fixture.

## Split

P0-86 reserved four SQL-behavior areas for this item:

| Slice | Status | Notes |
| --- | --- | --- |
| Group-key alias request slice | Complete | Python now has an explicit SQLite regression proving a request slice on a left-side alias can push to the RHS aggregate group key when the relation condition maps different field names. |
| Derived relation parameter binding and explain | Complete | Python now has a SQLite regression proving fixed RHS filters, pushed RHS WHERE, pushed aggregate HAVING, outer predicates, and EXPLAIN share deterministic placeholder params. Java fixture export is still recommended before broad contract freeze. |
| Relation-level RHS projection pruning/default measure aggregation | Complete | Python now prunes structured RHS aggregate projections to referenced output measures and keeps full RHS projection when raw SQL accessBuilder text is present. A broader Java fixture is still recommended before extending request-shape exposure. |
| Mixed OR and AND in/range predicate boundary | Complete | Python now keeps mixed OR join-key/measure predicates outer-only with retained diagnostics and preserves AND wrapper `in`/range pushdown to RHS WHERE/HAVING. A Java fixture export is still recommended before broad contract freeze. |

## First Slice Contract

The first slice covers this model shape:

- root QueryModel column `orderNo` maps to physical `fact_order.order_id`;
- aggregate relation RHS group key is `FactSalesModel.orderId`;
- relation condition maps `left_field=orderNo` to `right_field=orderId`;
- request slice filters `orderNo = :value`.

Expected behavior:

1. The outer query filters the root alias: `t1.order_id = ?`.
2. The RHS aggregate subquery also receives the pushed filter:
   `agg_src.order_id = ?`.
3. Params remain deterministic: fixed RHS filters first, pushed RHS params
   next, outer params last.
4. Pushdown diagnostics report the request field name (`orderNo`) and the RHS
   expression (`agg_src.order_id = ?`).
5. SQLite live-result execution returns the same aggregate row as the ordinary
   group-key path.

## Second Slice Contract

The second slice covers the Java evidence represented by
`AggregateJoinQueryModelTest#aggregateRelationShouldRunExplainWithPushedRightSideFilters`
and Java `docs/9.2.0/workitems/query-model-aggregate-join.md`: aggregate
relation derived SQL must expose bind values through the same parameter list
used by explain and execute.

Expected behavior:

1. Relation fixed filters render placeholders inside the RHS aggregate subquery,
   for example `agg_src.order_status = ?`.
2. Safe join-key request predicates push into the RHS grouped subquery as
   placeholders, for example `agg_src.order_id = ?`.
3. Aggregate output predicates push into RHS `HAVING` as placeholders, for
   example `having sum(agg_src.sales_amount) > ?`.
4. The outer query retains equivalent predicates over root and aggregate output
   aliases.
5. Params remain deterministic: relation fixed-filter params first, pushed RHS
   WHERE params next, pushed RHS HAVING params next, outer params last.
6. The rendered SQL contains placeholders only; request values and relation
   literals must not be inlined into the SQL string.
7. SQLite `EXPLAIN QUERY PLAN` can execute with the same SQL and param list that
   powers the live query.

## Third Slice Contract

The third slice covers Java
`AggregateJoinQueryModelTest#aggregateRelationShouldRenderDefaultMeasureAggregation`
and `#aggregateRelationRawSqlAccessBuilderShouldStayOuterOnly`, plus
`docs/9.2.0/workitems/query-model-aggregate-join.md` projection-pruning notes.

Expected behavior:

1. Structured aggregate relation requests render RHS group keys plus only the
   aggregate output measures referenced by `columns[]`, `slice`, or predefined
   calculated fields.
2. Default aggregate functions remain explicit, for example
   `sum(agg_src.sales_amount) salesAmount` and
   `count(distinct agg_src.customer_key) uniqueCustomers`.
3. Unreferenced aggregate measures are omitted from the RHS derived projection,
   for example `quantity` and `unitPrice` are not rendered when they are not
   requested.
4. Raw SQL `accessBuilder` / row-filter text disables RHS projection pruning
   because the renderer cannot infer references inside arbitrary SQL.
5. Raw SQL access predicates remain outer-only and are not pushed into the RHS
   aggregate subquery.

## Fourth Slice Contract

The fourth slice covers Java
`AggregateJoinQueryModelTest#aggregateRelationMixedOrSliceShouldStayOuterOnly`
and `#aggregateRelationAndInRangeSlicesShouldPushRightFilters`.

Expected behavior:

1. Mixed OR predicates that combine a left/root join key and an aggregate output
   measure remain in the outer query only.
2. Mixed OR does not copy the join-key predicate to RHS `WHERE`.
3. Mixed OR does not copy the aggregate-output predicate to RHS `HAVING`.
4. Retained diagnostics record each OR child with
   `OR_CONDITION_OUTER_ONLY`.
5. AND wrapper predicates keep the existing safe pushdown behavior:
   join-key `in` copies to RHS `WHERE`, aggregate-output range copies to RHS
   `HAVING`, and equivalent outer predicates remain in the root query.

## Implementation

- Added a focused test-only QueryModel,
  `OrderSalesAggregateRelationAliasKeyQueryModel`, whose left request field is
  intentionally named differently from the RHS group key.
- Added
  `test_p0_89_group_key_alias_request_slice_pushes_rhs_where(...)` in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.
- No production runtime code change was required for this first slice. The
  existing P0-85 pushdown path already resolves the relation condition's
  left-to-right field mapping correctly.
- Added
  `test_p0_89_derived_relation_params_explain_with_pushed_filters(...)` in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.
- No production runtime code change was required for the second slice. The
  existing relation SQL renderer already carries fixed RHS, pushed RHS, HAVING,
  and outer predicate params through one executable query body.
- Added relation-level RHS output-measure pruning to the narrow SQLite aggregate
  relation renderer in `src/foggy/dataset_model/semantic/service.py`.
- Added
  `test_p0_89_structured_request_prunes_unreferenced_rhs_measures(...)` and a
  focused wide-measure QueryModel helper in
  `tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`.
- Kept the existing
  `test_p0_87_raw_access_builder_stays_outer_only(...)` regression as the raw
  SQL accessBuilder fallback guard: it proves raw SQL predicates stay outer-only
  and full RHS projection is retained.
- Updated the aggregate relation OR renderer in
  `src/foggy/dataset_model/semantic/service.py` so outer-only OR predicates can
  resolve aggregate output aliases such as `fsByOrder.salesAmount`.
- Added
  `test_p0_89_mixed_or_join_key_and_measure_stays_outer_only(...)` to prove
  mixed OR stays outer-only, carries retained diagnostics, and executes against
  SQLite.
- Added
  `test_p0_89_and_wrapper_in_range_slices_push_rhs_filters(...)` to lock the
  explicit AND wrapper path for join-key `in` and aggregate-output range
  pushdown.

## Acceptance Criteria

- Completed. A request slice on the left alias is rendered as an outer root
  predicate.
- Completed. The same request slice is pushed into the RHS grouped subquery
  using the mapped RHS group key.
- Completed. Pushdown diagnostics stay deterministic and report the left
  request field plus RHS SQL expression.
- Completed. SQLite execution proves the alias-key slice returns the expected
  aggregate row.
- Completed. Derived relation parameter binding keeps fixed RHS filters, pushed
  join-key WHERE filters, pushed aggregate HAVING filters, and outer predicates
  as placeholders with deterministic params.
- Completed. SQLite `EXPLAIN QUERY PLAN` accepts the same SQL and params as the
  live aggregate relation query.
- Completed. Structured RHS projection pruning keeps requested default aggregate
  outputs and omits unreferenced aggregate measures.
- Completed. Raw SQL accessBuilder keeps full RHS projection and remains
  outer-only.
- Completed. Mixed OR join-key/measure predicates remain outer-only and produce
  retained diagnostics with `OR_CONDITION_OUTER_ONLY`.
- Completed. AND wrapper `in`/range predicates preserve safe RHS WHERE/HAVING
  pushdown and outer predicate retention.

## Verification

- Focused P0-89 first-slice test on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_group_key_alias_request_slice_pushes_rhs_where -q`
  (`1 passed in 0.52s`).
- Focused P0-89 second-slice test on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_derived_relation_params_explain_with_pushed_filters -q`
  (`1 passed in 0.54s`).
- Focused P0-89 third-slice pruning test on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_structured_request_prunes_unreferenced_rhs_measures -q`
  (`1 passed in 0.65s`).
- Focused P0-89 slice-only aggregate reference guard on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_slice_only_aggregate_ref_keeps_required_rhs_measure -q`
  (`1 passed in 0.62s`).
- Focused P0-89 raw access fallback guard on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_87_raw_access_builder_stays_outer_only -q`
  (`1 passed in 0.66s`).
- Focused predefined formula dependency guard on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_87_predefined_calculated_field_allowed_exec -q`
  (`1 passed in 0.66s`).
- Focused P0-89 fourth-slice mixed predicate tests on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_mixed_or_join_key_and_measure_stays_outer_only tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py::test_p0_89_and_wrapper_in_range_slices_push_rhs_filters -q`
  (`2 passed in 0.59s`).
- Aggregate relation focused suite on 2026-06-13:
  `.venv/bin/pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py -q`
  (`28 passed in 0.51s`).
- P0 aggregate relation combo on 2026-06-13:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`43 passed in 0.58s`).
- Static checks on 2026-06-13:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/semantic/service.py tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py`
  and `git diff --check` passed.
- Full Python baseline on 2026-06-13:
  `.venv/bin/python -m pytest -q`
  (`4155 passed, 232 skipped, 53 warnings in 19.76s`).

## Remaining Risks

- The group-key alias, derived relation parameter/explain, RHS projection
  pruning, and mixed predicate behaviors are proven by Python engine-neutral
  SQLite regressions and current Java documentation/test evidence, not yet by
  newly exported Java fixture cases.
- External aggregate relation dialects remain out of scope.
- Multi-relation stages, still-unsupported broader request stages, external
  dialects, and richer optimizer diagnostics still need fixture-backed
  contracts before runtime expansion. P0-95 later opened bounded aggregate
  output `orderBy` and `returnTotal` only for the narrow SQLite path.
