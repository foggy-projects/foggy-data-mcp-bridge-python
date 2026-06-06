# P0-4 Compose Script Tool Neutral Snapshot Replay Progress

Date: 2026-06-06

## Completed

- Added Java snapshot producer for `dataset.compose_script` runtime/tool
  parity.
- Generated `tests/fixtures/java_compose_script_snapshot_parity.json`.
- Added Python replay test for:
  - snapshot schema
  - MCP tool schema/description markers
  - Java runtime global surface coverage
  - literal return
  - empty plans envelope
  - preview-mode SQL capture
  - security-parameter fail-closed error
- Activated the manifest lane `compose-script-tool-snapshots`.

## Verification

Java:

```bash
mvn test -pl foggy-dataset-model -Dtest=JavaComposeScriptSnapshotTest
```

Result: passed. Maven ran the default, MySQL, and Postgres surefire executions
for this test; all passed.

Python:

```bash
.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py -q
```

Result: `4 passed in 0.41s`.

Manifest gate:

```bash
.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_compose_script_snapshot_parity.py -q
```

Result: `8 passed in 0.41s`.

Ruff:

```bash
.venv/bin/python -m ruff check tests/integration/test_java_compose_script_snapshot_parity.py
```

Result: passed.

Full baseline:

```bash
.venv/bin/python -m pytest --tb=short -q -rs
```

First run hit an intermittent failure in
`tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_resume`
(`run.suspension` was `None`). The failing test and the full
`test_suspend_limits.py` file both passed when rerun directly.

Second full run result: `4105 passed, 162 skipped, 43 warnings in 17.36s`.

## Remaining Follow-Ups

- Export and replay script execution row/DataSetResult shape.
- Export and replay MCP host-misconfig structured error payloads.
- Export and replay capability registry allow/deny errors.
- Decide whether Python's additional fsscript global surface should remain an
  accepted divergence or be tightened in a later security-focused item.
