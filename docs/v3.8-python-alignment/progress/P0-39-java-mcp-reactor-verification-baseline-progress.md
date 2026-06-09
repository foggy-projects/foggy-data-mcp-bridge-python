# P0-39 Java MCP Reactor Verification Baseline Progress

Date: 2026-06-09

## Completed

- Confirmed the `SemanticQueryRequest.OutputFormattingItem` /
  `getOutputFormatting()` symbols exist in the current Java source under
  `foggy-dataset-model`.
- Confirmed the old module-local command fails because it can resolve a stale
  local Maven artifact when `-am` is omitted.
- Re-ran the P0-34 Java exporter through the Maven reactor with upstream
  modules included.
- Re-ran `LocalDatasetAccessorGovernanceTest` through the Maven reactor to
  prove the previously reported compile blocker is not a source drift in the
  current worktree.
- Updated the Python alignment docs to use the reactor focused command as the
  Java MCP baseline.

## Verification

Passed:

- P0-34 Java exporter focused reactor verification:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test`
- Local accessor governance focused reactor verification:
  `mvn -q -pl foggy-dataset-mcp -am -Dtest=LocalDatasetAccessorGovernanceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected false blocker:

- The module-local command remains invalid for this workspace when the local
  Maven repository has an older `foggy-dataset-model` artifact:
  `mvn -q -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest test`
  failed during `testCompile` on
  `SemanticQueryRequest.OutputFormattingItem` / `getOutputFormatting()`.

## Notes

- No Java source code change was required.
- `LocalDatasetAccessorGovernanceTest` logs an ERROR stack trace for the
  invalid-slice fail-closed case while still passing; this is expected behavior
  for that test.
