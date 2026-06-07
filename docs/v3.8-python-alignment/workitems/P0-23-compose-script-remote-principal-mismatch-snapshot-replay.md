# P0-23 Compose Script Remote Principal-Mismatch Snapshot Replay

Date: 2026-06-07

## Goal

Extend the MCP compose-script error payload snapshot lane from host
misconfiguration into remote authority-binding fail-closed behavior.

This item adds the lowest-risk remote compose case whose Java/Python contract is
already aligned: a valid authority-binding envelope whose principal differs from
the request principal.

## Scope

- Java snapshot producer:
  `foggy-dataset-mcp/src/test/java/com/foggyframework/dataset/mcp/tools/JavaComposeScriptToolErrorSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_compose_script_tool_error_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `remote-principal-mismatch`
  - remote compose header is present
  - host-private `__foggyAuthorityBinding` envelope is present
  - envelope user is `u2`, request user is `u1`
  - payload is an error
  - `error_code` is `compose-authority-resolve/principal-mismatch`
  - `phase` is `permission-resolve`
  - no `model` field is present
  - message contains stable broad markers: `principal`, `differs`
  - payload does not leak stack/exception markers such as
    `NullPointerException`, `Traceback`, `Exception:`, or `at com.`

## Gap Decision

`remote-principal-mismatch` is aligned and safe to activate as snapshot replay.

`remote missing authority binding` remains out of scope for this item because
Java currently routes missing binding as
`compose-authority-resolve/invalid-response` in `permission-resolve`, while
Python returns `compose-authority-resolve/resolver-not-available` in
`authority-resolve`. That needs an explicit error-code/phase decision before it
is converted into replay.

## Acceptance

Required focused checks:

- Java exporter:
  `mvn test -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest`
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_compose_script_tool_error_snapshot_parity.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Current Verification

Blocked/passed:

- Java focused Maven execution remains blocked during module `testCompile` by
  existing `LocalDatasetAccessorGovernanceTest` drift:
  `SemanticQueryRequest.OutputFormattingItem` and `getOutputFormatting()` are
  missing from the current Java model class.
- The updated Java exporter compiles standalone with the module classpath and
  was executed through reflection to generate the two-case fixture.

Python verification is recorded in the matching progress file.

## Follow-Ups

- Decide remote missing authority-binding error-code/phase parity.
- Add missing context/header bridge payload snapshots.
- Add resolver factory exception payload snapshots after Java/Python behavior
  is explicitly aligned.
- Add capability registry fail-closed payload snapshots.
