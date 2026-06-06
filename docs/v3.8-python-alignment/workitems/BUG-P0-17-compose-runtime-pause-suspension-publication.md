---
type: bug
bug_source: regression-found
version: v3.8-python-alignment
ticket: BUG-P0-17
severity: major
status: ready-for-verification
reproduction_status: confirmed
test_strategy: integration-test
automation_decision: required
owner: python-compose-runtime
---

# BUG-P0-17 Compose Runtime Pause Suspension Publication

Date: 2026-06-06

## Background

P0-16 full Python baseline exposed intermittent failures in compose runtime
pause/resume tests. The failing tests all attempted to read
`run_ctx.suspension.suspend_id` immediately after observing
`run_ctx.state == SUSPENDED`.

The manager already exposes a safer public query boundary:
`get_active_suspension()` / `list_active_suspensions()`, where a suspension is
visible only after state, `SuspensionResult`, and wait slot are all present.

## Reproduction

Observed during P0-16 full baseline:

- `.venv/bin/python -m pytest -q`
  - `2 failed, 4039 passed, 232 skipped, 45 warnings in 17.58s`
- `.venv/bin/python -m pytest -q`
  - `1 failed, 4040 passed, 232 skipped, 43 warnings in 17.82s`

Failed tests:

- `tests/compose/runtime/test_handler_pause.py::TestFailClosed::test_resume_after_resume`
- `tests/compose/runtime/test_suspend_limits.py::TestResourceCleanup::test_cleanup_on_resume`
- `tests/compose/runtime/test_handler_pause.py::TestPureRuntimePause::test_reject_raises_in_handler`

Each failed with `AttributeError` because `run_ctx.suspension` was still
`None` when the test read `suspend_id`. Each failed test passed when rerun
directly.

## Expected vs Actual

Expected:

- Tests wait for a fully published suspension before reading `suspend_id`.
- Full baseline is not affected by a race between raw state visibility and
  suspension publication.

Actual:

- Tests used raw `ScriptRunContext.state` as the only readiness signal.
- Under full-suite scheduling, state could be observed before the suspension
  object was read-ready by the test thread.

## Impact Scope

- Affects Python compose runtime test stability.
- Does not change production pause/resume behavior.
- Does not affect Java snapshot parity fixtures.
- Blocks reliable alignment full-baseline evidence if left unfixed.

## Test Strategy

Automation is required because this is a regression-found baseline failure in
core compose runtime tests.

Coverage:

- Focused pause/resume runtime files:
  - `tests/compose/runtime/test_handler_pause.py`
  - `tests/compose/runtime/test_suspend_limits.py`
- Full compose runtime directory:
  - `tests/compose/runtime`
- Full Python pytest baseline.

## Code Inventory

- `tests/compose/runtime/test_handler_pause.py`
- `tests/compose/runtime/test_suspend_limits.py`

## Fix Checklist

- Add test helpers that wait through `SuspensionManager.get_active_suspension`
  and `SuspensionManager.list_active_suspensions`.
- Replace direct wait loops that immediately read `run_ctx.suspension`.
- Keep fail-closed resume/reject/timeout assertions unchanged.
- Clean local lint issues in the touched test files.
- Verify focused runtime tests, compose runtime suite, and full pytest.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/compose/runtime/test_handler_pause.py tests/compose/runtime/test_suspend_limits.py -q`
  - `24 passed in 0.29s`
- `.venv/bin/python -m ruff check tests/compose/runtime/test_handler_pause.py tests/compose/runtime/test_suspend_limits.py`
  - `All checks passed!`
- `.venv/bin/python -m pytest tests/compose/runtime -q`
  - `293 passed, 16 warnings in 1.01s`
- `.venv/bin/python -m pytest -q`
  - `4041 passed, 232 skipped, 43 warnings in 18.02s`

## References

- P0-16 progress:
  `docs/v3.8-python-alignment/progress/P0-16-pivot-domain-governance-snapshot-replay-progress.md`
