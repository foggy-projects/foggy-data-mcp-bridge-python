# P0-34 Compose Script Resolver Factory Exception Snapshot Replay

Date: 2026-06-09

## Goal

Close the remaining MCP compose-script resolver factory exception drift by
freezing Java's current structured error payload and replaying it in Python.

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

## Contract Covered

- `resolver-factory-exception`
  - script is present
  - `ToolExecutionContext` is present
  - embedded resolver factory raises a host-side runtime exception
  - payload is an error
  - `error_code` is `internal-error`
  - `phase` is `internal`
  - message contains `resolver`, `factory`, and `boom`
  - payload does not leak stack/exception markers

## Python Alignment Change

Before P0-34, Python classified resolver factory exceptions as
`host-misconfig/internal`. Java currently lets a generic resolver factory
runtime exception fall through to the broad runtime handler and returns
`internal-error/internal`.

P0-34 aligns Python to Java for generic resolver factory exceptions while
preserving resolver factory `None` as `host-misconfig/internal`.

## Non-Scope

- Changing remote authority-binding error contracts.
- Changing resolver `resolve(...)` permission errors.
- Reclassifying resolver factory `None`.
- Odoo business model or registry updates.

## Acceptance

Required focused checks:

- Java exporter standalone compile and reflection execution.
- Python replay, resolver factory unit checks, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_factory_raising_wraps_to_internal_error tests/test_mcp/test_compose_script_tool.py::test_factory_returning_none_is_host_misconfig tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
