# P0-25 Compose Script Input/Context Error Snapshot Replay

Date: 2026-06-07

## Goal

Close the Java/Python compose-script tool error-code drift for missing input
and missing context cases, and activate both in the Java snapshot replay lane.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
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

- `missing-script`
  - no `script` argument is present
  - payload is an error
  - `error_code` is `missing-script`
  - `phase` is `internal`
  - message contains stable broad markers: `script`, `required`
  - payload does not leak stack/exception markers
- `missing-context`
  - script is present
  - `ToolExecutionContext` is absent
  - payload is an error
  - `error_code` is `internal-error`
  - `phase` is `internal`
  - message contains stable broad markers: `ToolExecutionContext`, `required`
  - payload does not leak stack/exception markers

## Python Alignment Change

Before P0-25, Python returned `host-misconfig` for both missing script and
missing context. Java currently returns `missing-script` for missing script and
`internal-error` for a missing `ToolExecutionContext`.

P0-25 aligns Python with those Java contracts.

## Acceptance

Required focused checks:

- Java exporter standalone compile and reflection execution.
- Python replay, input/context unit checks, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_missing_script_argument_returns_error tests/test_mcp/test_compose_script_tool.py::test_empty_script_argument_returns_error tests/test_mcp/test_compose_script_tool.py::test_missing_context_returns_error tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Follow-Ups

- Add remaining header bridge payload snapshots.
- Add resolver factory exception payload snapshots after Java/Python contract
  ownership is clarified.
