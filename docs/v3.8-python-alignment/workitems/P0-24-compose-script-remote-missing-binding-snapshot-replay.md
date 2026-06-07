# P0-24 Compose Script Remote Missing Binding Snapshot Replay

Date: 2026-06-07

## Goal

Close the remote compose missing authority-binding error-code/phase drift and
activate it in the MCP compose-script Java snapshot replay lane.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
- Python tool:
  `src/foggy/mcp/tools/compose_script_tool.py`
- Python fixture:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
- Python binding test:
  `tests/test_mcp/test_compose_script_tool_binding.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `remote-missing-authority-binding`
  - remote compose header is present
  - host-private `__foggyAuthorityBinding` argument is absent
  - payload is an error
  - `error_code` is `compose-authority-resolve/invalid-response`
  - `phase` is `permission-resolve`
  - no `model` field is present
  - message contains stable broad markers: `authority`, `binding`
  - payload does not leak stack/exception markers such as
    `NullPointerException`, `Traceback`, `Exception:`, or `at com.`

## Python Alignment Change

Before P0-24, Python returned
`compose-authority-resolve/resolver-not-available` in `authority-resolve` for a
remote compose call with no binding envelope.

P0-24 aligns this with Java's current fail-closed contract:
`compose-authority-resolve/invalid-response` in `permission-resolve`.

## Acceptance

Required focused checks:

- Java exporter:
  `mvn test -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest`
- Python replay, binding test, and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool_binding.py::test_odoo_remote_compose_missing_envelope_fails tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/test_mcp/test_compose_script_tool_binding.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Current Verification

Blocked/passed:

- Java focused Maven execution remains blocked during module `testCompile` by
  existing `LocalDatasetAccessorGovernanceTest` drift:
  `SemanticQueryRequest.OutputFormattingItem` and `getOutputFormatting()` are
  missing from the current Java model class.
- The updated Java exporter compiles standalone with the module classpath and
  was executed through reflection to generate the three-case fixture.

Python verification is recorded in the matching progress file.

## Follow-Ups

- Add missing context/header bridge payload snapshots.
- Add resolver factory exception payload snapshots after Java/Python behavior
  is explicitly aligned.
- Add capability registry fail-closed payload snapshots.
