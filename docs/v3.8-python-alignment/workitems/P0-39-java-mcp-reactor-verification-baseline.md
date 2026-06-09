# P0-39 Java MCP Reactor Verification Baseline

Date: 2026-06-09

## Goal

Retire the recurring Java MCP `testCompile` false blocker from the Python
alignment evidence by documenting and validating the correct Maven reactor
command for MCP snapshot exporters.

## Scope

- Java MCP focused verification commands used by Python alignment work.
- P0-34 compose-script error snapshot exporter validation.
- `LocalDatasetAccessorGovernanceTest` compile/runtime validation in the same
  reactor context.
- Python v3.8 alignment documentation.

## Finding

The failing command:

```bash
mvn -q -pl foggy-dataset-mcp -Dtest=JavaComposeScriptToolErrorSnapshotTest test
```

does not build upstream reactor modules. It can resolve
`foggy-dataset-model` from the local Maven repository instead of the current
workspace source. When the installed artifact is older than the worktree, MCP
tests fail during `testCompile` on symbols that do exist in source, including
`SemanticQueryRequest.OutputFormattingItem` and `getOutputFormatting()`.

The correct focused command for this multi-module workspace is:

```bash
mvn -q -pl foggy-dataset-mcp -am -Dtest=JavaComposeScriptToolErrorSnapshotTest -Dsurefire.failIfNoSpecifiedTests=false test
```

`-am` builds required upstream modules from the current worktree, and
`-Dsurefire.failIfNoSpecifiedTests=false` avoids false failures in upstream
modules that do not contain the target test.

## Non-Scope

- Changing Java engine or MCP runtime behavior.
- Changing `LocalDatasetAccessorGovernanceTest` assertions.
- Installing or publishing new local Maven artifacts.
- Python engine code changes.

## Acceptance

- P0-34 Java exporter focused Maven verification passes with reactor `-am`.
- `LocalDatasetAccessorGovernanceTest` passes with reactor `-am`.
- P0-34 progress no longer presents the module-local `-pl` result as an
  unresolved source/test drift.
