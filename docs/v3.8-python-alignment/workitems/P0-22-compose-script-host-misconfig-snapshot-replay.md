# P0-22 Compose Script Host-Misconfig Snapshot Replay

Date: 2026-06-07

## Goal

Start MCP-level compose-script error payload parity with a low-risk,
engine-neutral host misconfiguration case.

This item freezes the shared structured payload contract for a resolver factory
that returns no resolver, without changing Python production behavior.

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

- `resolver-null-host-misconfig`
  - script argument is valid
  - resolver factory returns null/None
  - payload is an error
  - `error_code` is `host-misconfig`
  - `phase` is `internal`
  - no `model` field is present
  - message contains stable broad markers: `resolver`, `returned`
  - payload does not leak stack/exception markers such as
    `NullPointerException`, `Traceback`, `Exception:`, or `at com.`

## Python Gap Decision

Python already maps resolver-factory `None` to `host-misconfig/internal`.
P0-22 only commits Java snapshot evidence and Python replay.

Exact message text is not normalized in this item. The cross-language contract
is the structured payload plus broad message markers. Full message/error-code
normalization for missing script, missing context, resolver exceptions, and
remote binding failures remains a later host-misconfig matrix item.

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

- Java focused Maven execution is blocked during module `testCompile` by an
  existing `LocalDatasetAccessorGovernanceTest` drift:
  `SemanticQueryRequest.OutputFormattingItem` and `getOutputFormatting()` are
  missing from the current Java model class.
- The new Java exporter compiles standalone with the module classpath and was
  executed through reflection to generate the fixture.

Python verification is recorded in the matching progress file.

## Follow-Ups

- Decide whether Java `missing-script` and Python `host-misconfig` should
  converge or remain an accepted compatibility difference.
- Add missing context/header bridge payload snapshots.
- Add resolver factory exception payload snapshots.
- Add remote compose missing authority-binding payload snapshots.
- Add capability registry fail-closed payload snapshots.
