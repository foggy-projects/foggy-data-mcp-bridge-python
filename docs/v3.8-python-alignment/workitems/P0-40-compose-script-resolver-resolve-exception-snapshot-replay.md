# P0-40 Compose Script Resolver Resolve Exception Snapshot Replay

Date: 2026-06-09

## Goal

Close the MCP compose-script resolver `resolve(...)` generic exception gap by
freezing Java's current structured error payload and replaying it in Python.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contract Covered

- `resolver-resolve-exception`
  - script is present and references `FactSalesModel`
  - `ToolExecutionContext` is present
  - resolver factory returns a resolver
  - resolver `resolve(...)` raises a host-side runtime exception
  - payload is an error
  - `error_code` is `compose-authority-resolve/upstream-failure`
  - tool payload `phase` is `permission-resolve`
  - message contains `AuthorityResolver.resolve`, `unexpected exception`, and
    `details`
  - payload does not leak stack/exception markers

## Python Alignment Change

Python already wraps non-structured resolver `resolve(...)` exceptions as
`compose-authority-resolve/upstream-failure` in the authority pipeline. P0-40
adds Java snapshot replay coverage so this behavior is now locked against the
current Java MCP contract.

This intentionally differs from P0-34: resolver factory construction failures
stay `internal-error/internal`, while resolver invocation failures are
permission-resolution upstream failures.

## Non-Scope

- Changing resolver factory exception behavior.
- Changing remote authority-binding error contracts.
- Changing Odoo business models, generated bundles, or registry locks.
- Broad script runtime API expansion.

## Acceptance

Required focused checks:

- Java MCP exporter with reactor dependencies:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
