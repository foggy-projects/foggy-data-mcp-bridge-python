# P0-16 Pivot Domain Governance Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active governance snapshot lane with Pivot and domain transport
entry-point propagation evidence for `deniedColumns`.

This item is intentionally a low-risk alignment task. It exports Java neutral
contracts and replays them in Python without changing production engine
behavior and without touching Odoo business models.

## Scope

- Java snapshot producer:
  - `JavaGovernanceSnapshotTest.java`
- Python fixture:
  - `tests/fixtures/java_governance_snapshot_parity.json`
- Python replay:
  - `tests/integration/test_java_governance_snapshot_parity.py`
- Manifest:
  - `tests/fixtures/java_snapshot_parity_manifest.json`

## Contracts Covered

- Pivot row-axis relation field fails closed when the translated physical
  column is denied:
  - `pivot-denied-row-axis-refused`
- Pivot `parentShare` metric dependency fails closed when the native metric
  physical column is denied:
  - `pivot-parent-share-denied-native-metric-refused`
- Domain transport request with an internal carrier still fails closed under
  query validation before transport SQL rendering:
  - `domain-transport-denied-domain-column-refused`

## Python Gap Decision

Python already validates these paths through `SemanticQueryService` and the
existing field-access permission step. P0-16 records that behavior as replayed
Java parity evidence instead of introducing new production logic.

## Acceptance

Required focused checks:

- Java exporter:
  `JAVA_HOME=/Users/fengjianguang/.jdk/temurin-17/Contents/Home mvn -pl foggy-dataset-model -am -P'!multi-db' -Dspring.profiles.active=sqlite -Dtest='JavaGovernanceSnapshotTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test`
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_governance_snapshot_parity.py -q`
- Manifest replay:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_governance_snapshot_parity.py -q`
- Scoped lint:
  `.venv/bin/python -m ruff check tests/integration/test_java_governance_snapshot_parity.py`

## Current Verification

Passed:

- Java exporter:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python focused replay:
  `2 passed in 0.64s`
- Manifest replay:
  `6 passed in 0.66s`
- Scoped ruff:
  `All checks passed!`
- Targeted rerun of two full-baseline failures:
  `2 passed in 0.03s`
- Targeted rerun of the second full-baseline failure:
  `1 passed in 0.03s`

Full baseline note:

- `.venv/bin/python -m pytest -q` first run failed with two compose runtime
  pause/resume tests:
  - `tests/compose/runtime/test_handler_pause.py::TestFailClosed::test_resume_after_resume`
  - `tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_resume`
- Both failures were `AttributeError` after a thread-side
  `ScriptSuspendTimeoutError`. The same two tests passed when rerun directly.
- A second full run failed in
  `tests/compose/runtime/test_handler_pause.py::TestPureRuntimePause::test_reject_raises_in_handler`
  with the same `run_ctx.suspension` not-ready symptom. That test also passed
  when rerun directly.

## Follow-Ups

- Add authority-resolved visible model allow/deny snapshots.
- Add cross-model calculated-field governance refusal snapshots.
- Add sanitized error payload snapshots that prove physical-column details do
  not leak.
- Keep aggregate-join governance as P2 with the aggregate-join design line.
