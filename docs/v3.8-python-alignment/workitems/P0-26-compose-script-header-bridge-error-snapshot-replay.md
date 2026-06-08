# P0-26 Compose Script Header Bridge Error Snapshot Replay

Date: 2026-06-08

## Goal

Close the Java/Python compose-script header bridge error-code drift for missing
header-mode principal and namespace cases.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
- Python context bridge:
  `src/foggy/dataset_model/engine/compose/runtime/context_bridge.py`
- Python tool:
  `src/foggy/mcp/tools/compose_script_tool.py`
- Python fixture:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
- Python unit coverage:
  `tests/test_mcp/test_compose_script_tool.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `missing-user-id-header`
  - script is present
  - context namespace is present
  - `X-User-Id` / `user_id` is absent
  - payload is an error
  - `error_code` is `internal-error`
  - `phase` is `internal`
  - message contains `X-User-Id` and `required`
  - payload does not leak stack/exception markers
- `missing-namespace-header`
  - script is present
  - principal header is present
  - context namespace and `X-Namespace` are absent
  - payload is an error
  - `error_code` is `internal-error`
  - `phase` is `internal`
  - message contains `X-Namespace` and `required`
  - payload does not leak stack/exception markers

## Python Alignment Change

Before P0-26, Python returned `host-misconfig` for context bridge
`ValueError` / `TypeError` cases. Java currently lets these bridge failures
fall through to broad runtime handling and returns `internal-error`.

P0-26 aligns the Python header bridge cases with Java while preserving
resolver factory failures as `host-misconfig`.

## Acceptance

Required focused checks:

- Java exporter standalone compile and reflection execution.
- Python replay, header bridge unit checks, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_missing_user_id_bridges_to_internal_error tests/test_mcp/test_compose_script_tool.py::test_missing_namespace_bridges_to_internal_error tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check src/foggy/dataset_model/engine/compose/runtime/script_runtime.py src/foggy/dataset_model/engine/compose/runtime/context_bridge.py src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Follow-Ups

- Resolver factory exception payload snapshots remain separate because Java and
  Python currently classify them differently.
