# P0-4 Compose Script Tool Neutral Snapshot Replay

Status: implemented

Date: 2026-06-06

## Goal

Activate the first Java-to-Python parity lane for `dataset.compose_script`
without touching production engine code or Odoo business models.

This work item covers a narrow, stable contract:

- Java MCP resource markers for `dataset.compose_script`.
- Java runtime visible global surface.
- Basic script success results.
- Preview-mode SQL capture shape.
- Fail-closed security-parameter rejection.
- Forbidden legacy result-object markers for the current SemanticDSL tool
  surface.

## Scope

In scope:

- Java snapshot producer:
  `foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/engine/compose/runtime/JavaComposeScriptSnapshotTest.java`
- Python fixture:
  `tests/fixtures/java_compose_script_snapshot_parity.json`
- Python replay:
  `tests/integration/test_java_compose_script_snapshot_parity.py`
- Manifest lane activation in:
  `tests/fixtures/java_snapshot_parity_manifest.json`

Out of scope for this slice:

- Odoo model/domain fixtures.
- Legacy Java `DataSetResult`/`ComposedDataSetResult` method-surface parity.
  P0-21 covers the narrower execute-mode rows envelope for the current
  QueryPlan-envelope contract.
- Capability registry allow/deny snapshots.
- MCP host-misconfig payload snapshots beyond resource/schema markers.

## Notes

Java currently locks script globals to `{from, dsl, Query, subquery}`. Python
also exposes fsscript builtins and `params`. This is recorded in the snapshot as
an accepted Python extra surface for P0-4, not treated as a failure.

Preview-mode SQL uses Java/Python stub semantic services that preserve model and
plan-shape markers, so the replay validates runtime plan interception and
SQL-capture shape rather than model SQL generation.

The fixture deliberately requires Python's `dataset.compose_script` tool
description/schema to omit legacy Java result-object names such as
`DataSetResult`, `ComposedDataSetResult`, `toList`, `withJoin`, and
`joinInMemory`. Those APIs are not part of the current AI-facing SemanticDSL
script contract.

## Acceptance

- Java producer passes with:
  `mvn test -pl foggy-dataset-model -Dtest=JavaComposeScriptSnapshotTest`
- Python replay passes with:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py -q`
- Manifest gate includes the active `compose-script-tool-snapshots` lane.
