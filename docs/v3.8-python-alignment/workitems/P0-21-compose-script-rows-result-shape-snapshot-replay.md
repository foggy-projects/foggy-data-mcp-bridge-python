# P0-21 Compose Script Rows Result Shape Snapshot Replay

Date: 2026-06-07

## Goal

Close the first script runtime result-shape gap after P0-4 by replaying a Java
execute-mode `dsl(...)` plan envelope in Python.

This item records the shared contract that `return { plans: dsl(...) }` returns
row data in execute mode, while preview mode continues to return `ComposedSql`.

## Scope

- Java snapshot producer:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/runtime/JavaComposeScriptSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_compose_script_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_snapshot_parity.py`
- Manifest:
  `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- `execute-base-plan-rows-envelope`
  - script returns `{ plans: dsl(...) }`
  - `previewMode=false`
  - Java `plans` value is a row list from `QueryPlan.execute()`
  - Python replay expects the same canonical row list:
    `[{"stub": 1}]`

## Python Gap Decision

Python already returns row lists for execute-mode plan envelopes through the
existing script runtime and stub semantic service. P0-21 adds Java parity
evidence and keeps the behavior under the active compose-script snapshot lane.

This item does not claim full Java `DataSetResult` or `ComposedDataSetResult`
method-surface parity. The current script tool contract is QueryPlan-envelope
based, so legacy result-object methods stay outside the P0 alignment target
unless product explicitly reopens that API.

## Acceptance

Required focused checks:

- Java exporter:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeScriptSnapshotTest`
- Python replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
- Scoped lint:
  `.venv/bin/ruff check tests/integration/test_java_compose_script_snapshot_parity.py`
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Current Verification

Passed:

- Java exporter:
  - default, MySQL, and Postgres surefire executions passed with
    `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python replay plus manifest:
  `8 passed in 0.45s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4049 passed, 232 skipped, 43 warnings in 17.75s`

## Follow-Ups

- Reopen `DataSetResult`/`ComposedDataSetResult` method and composed-result
  shape only if Java exposes that contract through the script tool.
- Export and replay MCP host-misconfig structured error payloads.
- Export and replay capability registry allow/deny errors.
