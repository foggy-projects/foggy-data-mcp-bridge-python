---
doc_purpose: Track loader-side aggregate relation carrier extraction while runtime remains fail-closed.
version: v3.8-python-alignment
priority: P0-78
status: implemented
owner: python-engine
---

# P0-78 QueryModel Aggregate Loader Carrier Boundary

Date: 2026-06-11

## Background

P0-77 added the proxy/model carrier for QueryModel aggregate joins. The next
alignment step is to let the loader normalize recognized aggregate join
declarations into carriers without accidentally loading or executing them.

## Delivered

- Added loader helper `_extract_aggregate_relation_carriers(...)`.
- Supported carrier extraction from:
  - explicit `aggregateJoin` / `aggregateJoins` / `aggregateRelation*` dicts
  - Java-compatible `leftJoinAggregate(...)` DSL objects
- Reused the same QM model-reference resolver for ordinary QM loading and
  aggregate carrier extraction.
- Updated aggregate join refusal messages with `carrier_count=N`, proving the
  loader recognized a structured aggregate relation before failing closed.

## Boundary

- QueryModel aggregate joins still do not load as runtime models.
- `_reject_unsupported_aggregate_join_contract(...)` still raises
  `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`.
- Ordinary explicit joins still use `ExplicitJoinDef`; aggregate carriers are
  not converted into ordinary joins.
- SQL lowering, permission propagation, diagnostics output, metadata exposure,
  and live-result parity remain deferred.

## Verification

- `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -k "aggregate_relation_carrier or aggregate_join_explicit_contract_fails_closed or left_join_aggregate_dsl_fails_closed" -q`
  passed with `4 passed, 62 deselected`.
- `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
  passed with `66 passed`.
- `.venv/bin/python -m pytest tests/test_dataset_model/test_table_model_proxy.py -q`
  passed with `40 passed`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed`.
- `git diff --check` passed.

## Next

P0-79 should add a compiler/runtime boundary test that refuses any model carrying
`aggregate_relations` before SQL lowering exists. This keeps the future loader
attachment safe when the first non-rejecting parser path is introduced.
