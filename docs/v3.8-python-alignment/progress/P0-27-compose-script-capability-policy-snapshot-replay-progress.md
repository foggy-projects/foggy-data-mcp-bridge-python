# P0-27 Compose Script Capability Policy Snapshot Replay Progress

Date: 2026-06-08

## Completed

- Extended `JavaComposeScriptSnapshotTest` with:
  - `capability-pure-runtime-policy-allow`
  - `capability-pure-runtime-policy-deny`
- Regenerated
  `tests/fixtures/java_compose_script_snapshot_parity.json` with capability
  allow/deny cases.
- Updated Python replay to construct the Java-described `fiscalYear`
  registry/policy pair per snapshot case.
- Added Python runtime preflight for registered-but-denied runtime capability
  calls.
- Updated the Java snapshot manifest and alignment docs.

## Verification

Passed:

- Java focused Maven execution:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest=JavaComposeScriptSnapshotTest -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
  - result: `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python runtime replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_snapshot_parity.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `8 passed in 0.53s`
- Python P0-26/P0-27 focused replay and manifest:
  `.venv/bin/python -m pytest tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py::test_missing_user_id_bridges_to_internal_error tests/test_mcp/test_compose_script_tool.py::test_missing_namespace_bridges_to_internal_error tests/integration/test_java_snapshot_parity_manifest.py -q`
  - result: `12 passed, 8 warnings in 0.52s`
- Full Python pytest baseline:
  `4053 passed, 232 skipped, 51 warnings in 17.72s`

Blocked:

- Scoped ruff on touched files:
  `.venv/bin/ruff check src/foggy/dataset_model/engine/compose/runtime/script_runtime.py src/foggy/dataset_model/engine/compose/runtime/context_bridge.py src/foggy/mcp/tools/compose_script_tool.py tests/integration/test_java_compose_script_tool_error_snapshot_parity.py tests/integration/test_java_compose_script_snapshot_parity.py tests/test_mcp/test_compose_script_tool.py`
  - blocked by existing file-wide typing-modernization and unused-import debt
  - final run reported 66 errors after import-order fixes

## Notes

- Java's denied capability path reports the missing function name in a localized
  fsscript message. Python now reports a named capability denial before the
  evaluator reaches the generic null-call branch.
