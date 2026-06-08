# P0-27 Compose Script Capability Policy Snapshot Replay

Date: 2026-06-08

## Goal

Add Java/Python parity coverage for compose-script `pure_runtime` capability
policy allow/deny behavior.

## Scope

- Java snapshot producer:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/runtime/JavaComposeScriptSnapshotTest.java`
- Python runtime:
  `src/foggy/dataset_model/engine/compose/runtime/script_runtime.py`
- Python fixture:
  `tests/fixtures/java_compose_script_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_snapshot_parity.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `capability-pure-runtime-policy-allow`
  - registry defines `fiscalYear(month)` as `pure_runtime`
  - policy allows `fiscalYear`
  - script `return fiscalYear(4);` returns `2025`
- `capability-pure-runtime-policy-deny`
  - registry defines `fiscalYear(month)` as `pure_runtime`
  - policy is empty
  - script fails closed
  - error message contains `fiscalYear`

## Python Alignment Change

Python previously omitted denied capabilities from the evaluator context and
let fsscript surface a generic null-call error. P0-27 adds a runtime preflight
for registered-but-denied compose runtime function calls so denial remains
fail-closed and names the capability.

Default behavior without an explicit registry/policy pair remains unchanged:
no capability entries are injected.

## Acceptance

Required focused checks:

- Java runtime exporter standalone compile and reflection execution.
- Python runtime replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Full P0-26/P0-27 focused set:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_missing_user_id_bridges_to_internal_error tests/test_mcp/test_compose_script_tool.py::test_missing_namespace_bridges_to_internal_error tests/integration/test_java_snapshot_parity_manifest.py -q`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Follow-Ups

- Object facade capability allow/deny snapshots.
- SQL scalar capability snapshots in formula/compose-column surfaces.
