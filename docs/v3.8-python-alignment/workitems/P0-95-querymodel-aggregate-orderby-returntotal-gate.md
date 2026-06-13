---
doc_purpose: Track bounded orderBy and returnTotal support for Python QueryModel aggregate relations.
version: v3.8-python-alignment
priority: P0-95
status: complete
owner: python-engine
---

# P0-95 QueryModel Aggregate orderBy / returnTotal Gate

Date: 2026-06-13

## Scope

P0-95 opens two previously refused aggregate relation stages after Java v3
fixture evidence exists:

- `orderBy` on aggregate relation output aliases.
- `returnTotal` over the narrow SQLite aggregate relation query.

The implementation remains fail-closed for `groupBy`, `having`, post stages,
`timeWindow`, `pivot`, external dialect expansion, and Odoo business models.

## Implementation

- Added `QueryBuildResult.total_sql` and `total_params`.
- Added aggregate relation `orderBy` rendering on the outer query, using
  aggregate output aliases such as `fsByOrder.salesAmount` instead of RHS
  physical fields.
- Included `orderBy` aggregate aliases in the RHS measure-retention analysis so
  a sorted aggregate output is not pruned from the RHS derived query.
- Added `returnTotal` total SQL generation using a `from (...) tx` wrapper,
  summing numeric root fields, aggregating aggregate outputs, and appending
  `count(*) "total"`.
- Execute mode now runs the total SQL when present and fills
  `response.total` plus `response.total_data`.
- Validate and execute debug payloads expose `totalSql` and `totalParams`.
- Updated the prior P0-90 refusal tests so `orderBy` and `returnTotal` are no
  longer treated as refused request stages.

## Verification

- Focused aggregate runtime/refusal command:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
- Result: `45 passed in 0.78s`.
- Java replay command:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
- Result: `10 passed in 0.05s`.
- Combined aggregate runtime/refusal plus Java v3 replay command:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
- Result: `55 passed in 0.62s`.
- Static checks:
  `.venv/bin/ruff check --select F src/foggy/dataset_model/semantic/service.py src/foggy/dataset_model/semantic/field_validator.py src/foggy/dataset_model/aggregate_join.py tests/test_dataset_model/test_querymodel_aggregate_sqlite_alignment.py tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`
  and `git diff --check` both passed.

## Remaining Boundary

`returnTotal` is implemented for the narrow SQLite aggregate relation shape and
selected numeric/aggregate outputs. It is not a claim of broad QueryModel total
parity for post stages, pivot/timeWindow combinations, multi-relation aggregate
joins, or non-SQLite dialects.
