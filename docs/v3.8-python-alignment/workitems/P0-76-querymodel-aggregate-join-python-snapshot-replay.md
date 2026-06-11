---
doc_purpose: Track Python replay activation for the Java QueryModel aggregate join neutral snapshot.
version: v3.8-python-alignment
priority: P0-76
status: implemented
owner: python-engine
---

# P0-76 QueryModel Aggregate Join Python Snapshot Replay

Date: 2026-06-11

## Background

P0-75 added the Java exporter for QueryModel aggregate join neutral snapshots.
P0-76 promotes the generated Java snapshot into the Python repository and makes
the replay lane active without implementing Python aggregate join SQL lowering.

## Delivered

- Added committed fixture:
  `tests/fixtures/java_querymodel_aggregate_join_snapshot_parity.json`.
- Added replay harness:
  `tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py`.
- Updated manifest lane `querymodel-aggregate-join-neutral-snapshots` from
  `planned` to `active`.
- Updated contract test expectations so the lane now requires both the contract
  fixture and committed Java parity fixture.

## Replay Scope

- Snapshot envelope: schema, feature, source, contract version, dialect, and
  the 10 required case ids.
- Java result evidence for left-measure non-multiplication.
- SQL marker and forbidden-marker checks for RHS preaggregation, fixed filters,
  runtime filters, AND pushdown, and OR outer-only behavior.
- Fail-closed error code and message marker checks.
- Aggregate relation diagnostics for pushed and retained predicates.
- Metadata lineage keys for aggregate outputs.

## Boundary

- Python production aggregate join remains unimplemented.
- Existing P1-2 loader/proxy fail-closed behavior remains the runtime boundary.
- No Odoo business model or generated model refresh is included.
- Live SQLite result parity in Python is deferred until the aggregate relation
  carrier and SQL lowering are implemented.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  passed with `10 passed`.
- `git diff --check` passed.

## Next

P0-77 should start the minimal Python aggregate relation carrier design and
implementation boundary: parse/load a neutral carrier without compiling SQL
yet, keep fail-closed behavior for unsupported shapes, and prepare the lowering
surface for the committed Java fixture.
