---
doc_purpose: Track guarded loader attachment for QueryModel aggregate relation carriers.
version: v3.8-python-alignment
priority: P0-80
status: completed
owner: python-engine
---

# P0-80 QueryModel Aggregate Loader Attachment Boundary

Date: 2026-06-12

## Background

P0-79 added a semantic-service refusal boundary for any model carrying
`aggregate_relations`. P0-80 uses that boundary to safely open a controlled
loader path: the loader can now attach parsed aggregate relation carriers to a
QueryModel alias only when explicitly requested, while default production
loading remains fail-closed.

## Target Outcome

- Default `load_models_from_directory(...)` behavior still rejects recognized
  QueryModel aggregate joins with `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED`.
- An explicit guarded path can attach parsed aggregate relation carriers to the
  QM alias model for parity tests and later compiler work.
- Java-style `leftJoinAggregate(...)` DSL sentinels are not loaded as ordinary
  explicit joins.
- Runtime and compiler paths still fail closed before SQL generation through
  the P0-79 boundary.

## Implementation

- Added `attach_aggregate_relations: bool = False` to
  `load_models_from_directory(...)`.
- When the flag is false, existing fail-closed loader behavior is preserved.
- When the flag is true, the loader:
  - extracts aggregate relation carriers from explicit contract dicts and
    Java-style DSL sentinels,
  - attaches them to `alias_model.aggregate_relations`,
  - skips aggregate relation sentinels while building ordinary
    `explicit_joins`.
- Added a carrier-extraction guard for recognized aggregate join declarations
  that cannot produce a carrier.

## Acceptance Criteria

- Completed. Default loader path still fails closed for aggregate join
  declarations and reports `carrier_count=1`.
- Completed. Guarded loader path can produce a QM alias model with
  `aggregate_relations`.
- Completed. Java-style `leftJoinAggregate(...)` carrier is attached without
  becoming an ordinary explicit join.
- Completed. Semantic query validate still fails closed with sanitized
  `QUERYMODEL_AGGREGATE_JOIN_UNSUPPORTED` before SQL generation.

## Verification

- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_loader_fsscript.py -q`
  (`68 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/test_dataset_model/test_querymodel_aggregate_runtime_refusal.py -q`
  (`5 passed`)
- Passed:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_querymodel_aggregate_join_snapshot_contract.py tests/integration/test_java_querymodel_aggregate_join_snapshot_parity.py -q`
  (`10 passed`)

## Execution Check-in

- Code paths touched:
  - `src/foggy/dataset_model/impl/loader/__init__.py`
  - `tests/test_dataset_model/test_loader_fsscript.py`
- Self-check:
  - The new loader behavior is opt-in.
  - Aggregate relation carriers are structurally preserved.
  - Ordinary explicit join metadata remains separate from aggregate relation
    carriers.
  - Runtime exposure remains blocked by P0-79.

## Next

P0-81 should define the minimal SQLite happy-path SQL shape before SQL lowering
is implemented. The design must be based on the committed Java aggregate-join
snapshot and must keep governance, metadata, and diagnostics for P0-84/P0-85.
