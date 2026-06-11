---
doc_purpose: Track the minimal Python aggregate relation carrier boundary for QueryModel aggregate join alignment.
version: v3.8-python-alignment
priority: P0-77
status: implemented
owner: python-engine
---

# P0-77 QueryModel Aggregate Relation Carrier

Date: 2026-06-11

## Background

P0-76 activated replay for the Java QueryModel aggregate join neutral snapshot.
Python still failed closed for aggregate join declarations, but the DSL sentinel
discarded relation details. P0-77 adds a minimal structural carrier so Python
can preserve the aggregate relation contract before SQL lowering is implemented.

## Delivered

- Added aggregate relation model classes in
  `src/foggy/dataset_model/impl/model/__init__.py`:
  - `AggregateRelationDef`
  - `AggregateRelationConditionDef`
  - `AggregateRelationFilterDef`
  - `AggregateRelationMeasureDef`
- Added `DbTableModelImpl.aggregate_relations` as the model landing point.
- Upgraded the Java-compatible `leftJoinAggregate(...)` and aggregate relation
  proxy sentinel in `src/foggy/dataset_model/proxy/__init__.py` to capture:
  - RHS filters
  - RHS group keys
  - aggregate measures
  - relation alias
  - join conditions
- Kept `aggregate_join_unsupported=True` on the carrier/proxy path, so loader
  and compiler behavior remains fail-closed.

## Boundary

- No aggregate join SQL lowering is enabled.
- No runtime execution path consumes `aggregate_relations` yet.
- Existing unsupported declaration checks still reject aggregate join QMs instead
  of loading them as ordinary explicit joins.
- No Odoo business model or generated registry model refresh is included.

## Verification

- `.venv/bin/python -m pytest tests/test_dataset_model/test_table_model_proxy.py -q`
  passed with `40 passed`.
- `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -k "aggregate_join_explicit_contract_fails_closed or left_join_aggregate_dsl_fails_closed" -q`
  passed with `2 passed, 62 deselected`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed`.
- `git diff --check` passed.

## Next

P0-78 should attach aggregate relation declarations to the loader boundary in a
controlled way while preserving fail-closed runtime behavior. SQL lowering,
permission propagation, diagnostics, and live SQLite result parity should stay
behind the Java snapshot replay gate.
