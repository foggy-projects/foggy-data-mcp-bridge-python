---
doc_purpose: Define the minimal SQLite SQL-shape for QueryModel aggregate relation lowering.
version: v3.8-python-alignment
priority: P0-81
status: completed
owner: python-engine
---

# P0-81 QueryModel Aggregate SQLite SQL-Shape Design

Date: 2026-06-12

## Background

P0-79 and P0-80 make aggregate relation carriers visible to the Python engine
behind a refusal boundary. P0-81 defines the first SQL lowering shape before
any implementation opens runtime behavior.

The design source is the committed Java fixture:

- `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`
- source case `aggregate-join-sql-shape-sqlite`
- source case `aggregate-join-fixed-rhs-filter`

## Scope

P0-82 should implement only this SQLite SQL-shape skeleton:

- one left root model,
- one aggregate relation,
- `LEFT JOIN` from the root model to one RHS grouped subquery,
- fixed RHS filters with literal bind parameters,
- RHS `GROUP BY` that covers the right join key,
- RHS aggregate outputs projected from the relation alias,
- no runtime extData filters,
- no OR/mixed pushdown diagnostics,
- no governance/metadata lineage behavior yet.

Everything else remains fail-closed until P0-83/P0-84/P0-85.

## Java Shape Contract

### Minimal Count/Sum Shape

Source fixture: `aggregate-join-sql-shape-sqlite`.

Required normalized SQL markers:

- root table: `fact_order`
- relation table: `fact_sales`
- join form: `left join (select ... from fact_sales agg_src ... group by ...)`
- RHS alias: fallback alias equivalent to `t2`
- RHS source alias: `agg_src`
- fixed filter: `agg_src.order_status = ?`
- aggregate outputs:
  - `sum(agg_src.sales_amount) salesAggAmount`
  - `count(*) salesLineCount`
- join condition: left physical order id equals RHS grouped order id.

Forbidden markers:

- `count(distinct`
- `.salesAmount`

Expected params:

- `["COMPLETED"]`

### Explicit Aggregate Relation Alias Shape

Source fixture: `aggregate-join-fixed-rhs-filter`.

Required normalized SQL markers:

- RHS relation alias: `fsByOrder`
- RHS source alias: `agg_src`
- fixed filter: `agg_src.order_status = ?`
- group clause: `group by agg_src.order_id`
- aggregate output: `sum(agg_src.sales_amount) salesAmount`
- optional distinct output:
  `count(distinct agg_src.customer_key) uniqueCustomers`
- join condition:
  root physical `order_id` equals `fsByOrder.orderId`.

Forbidden markers:

- `sum(agg_src.quantity) quantity`

Expected params:

- `["COMPLETED"]`

## Lowering Rules

### Root Projection

Root fields continue to resolve through the existing QueryModel field mapping:

- root dimensions/properties are projected from the root alias,
- root measures without a relation owner are projected from the root alias,
- root output aliases remain the requested semantic names.

For the Java fixture shape:

- `orderId` maps to `fact_order.order_id`,
- `amount` maps to `fact_order.total_amount`.

### Aggregate Relation Projection

Fields produced by `AggregateRelationDef.measures` are owned by the aggregate
relation and must be projected from the relation alias, not from the root table.

For example:

- `salesAmount` -> `fsByOrder.salesAmount`
- `uniqueCustomers` -> `fsByOrder.uniqueCustomers`
- `salesAggAmount` -> fallback relation alias output

The RHS subquery must render the aggregate expression from the source model's
physical columns:

- `SUM` -> `sum(agg_src.<physical_column>)`
- `COUNT` with no source field -> `count(*)`
- `COUNT_DISTINCT` or `distinct=true` -> `count(distinct agg_src.<physical_column>)`

### Join Key Rule

The RHS `GROUP BY` must include every right-side join key referenced by the
relation conditions. If it does not, lowering must fail closed with:

- `QUERYMODEL_AGGREGATE_JOIN_GROUPBY_MISSING_RIGHT_KEY`

This refusal is already required by the Java fixture and should land before or
with the first lowering skeleton.

### Fixed Filter Rule

P0-82 may support fixed RHS filters only when all of these are true:

- filter model is the aggregate relation right model or omitted,
- operator is `=` or `in`,
- value is a literal list/scalar, not a runtime expression,
- field resolves to a right model physical column.

Unsupported filter shapes must fail closed with a
`QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`-family message and must not fall back
to outer WHERE behavior.

### Parameter Order

For the P0-82 fixed-filter subset, params are emitted in RHS subquery order:

1. fixed RHS filters,
2. later P0-83/P0-85 runtime/pushdown params,
3. outer/root filters.

P0-82 only needs step 1.

## Implementation Notes For P0-82

- Keep the renderer SQLite-only until the Java fixture has been replayed.
- Prefer a small aggregate-relation renderer instead of mutating ordinary
  explicit join lowering.
- Keep P0-79 refusal for unsupported aggregate relation shapes.
- Do not route aggregate relation fields through ordinary measure resolution;
  that would produce forbidden semantic-field markers such as `.salesAmount`.
- Keep result execution disabled unless P0-83 adds the SQLite fixture setup and
  oracle checks.

## Verification Plan

P0-82 should add focused SQL-shape tests that compare markers against the Java
fixture cases:

- `aggregate-join-sql-shape-sqlite`
- `aggregate-join-fixed-rhs-filter`

Required checks:

- `left join` appears.
- RHS grouped subquery appears.
- `agg_src.order_status = ?` appears.
- `group by agg_src.order_id` appears.
- expected aggregate expressions appear.
- forbidden markers do not appear.
- params match `["COMPLETED"]`.
- unsupported/missing right key groupBy fails closed.

## Execution Check-in

- No runtime code changed in P0-81.
- This design intentionally limits P0-82 to SQL-shape evidence.
- P0-83 is responsible for SQLite live-result parity and non-multiplication
  result checks.
- P0-84 and P0-85 remain responsible for governance/metadata and pushdown
  diagnostics respectively.
