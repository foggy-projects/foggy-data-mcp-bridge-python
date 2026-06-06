# P0-2 Java Snapshot Parity Manifest

Version: v3.8-python-alignment
Priority: P0
Status: ready for acceptance
Owner: Python engine
Date: 2026-06-06

## Purpose

Create a small executable manifest gate for Python alignment work so P0 can
track which Java snapshot lanes already have Python evidence and which lanes
still need Java exports.

This is intentionally not a production engine change. The first goal is to make
parity evidence discoverable and testable before implementing larger compose,
pivot, domain transport, registry, or Odoo-facing changes.

## Scope

In scope:

- Register existing active Java/Python parity evidence for formula and
  timeWindow.
- Register planned Java export requirements for compose query, script runtime
  tool, pivot/domain transport, governance, and neutral domain fixtures.
- Add a pytest manifest gate that validates active fixture/test paths and
  planned export checklists.

Out of scope:

- Generating new Java snapshots in this repo.
- Changing production Python engine behavior.
- Touching Odoo generated models or registry bundles.
- Requiring live MySQL/Postgres/SQL Server services.

## Acceptance Criteria

- `tests/fixtures/java_snapshot_parity_manifest.json` exists and contains both
  active and planned parity lanes.
- Active entries point to real Python fixtures, committed snapshots, and tests.
- Active Java-owned resources are resolved from `FOGGY_JAVA_WORKTREE` or known
  sibling Java worktrees.
- Planned entries have explicit Java export requirements and reserved Python
  replay test targets.
- Focused pytest for the manifest gate passes locally.

## Implementation Notes

Use `active` only for lanes with existing executable evidence. Use `planned` for
P0/P1 lanes that still require Java snapshot exports. This keeps the local full
pytest baseline green while making missing Java exports visible in docs and in
the manifest.

## Test Evidence

- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py -q --tb=short`
  passed: `4 passed in 0.03s`.
- `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_formula_parity.py tests/test_dataset_model/test_time_window_java_parity_catalog.py tests/integration/test_time_window_golden_diff.py -q --tb=short -rs`
  passed: `74 passed in 0.54s`.
