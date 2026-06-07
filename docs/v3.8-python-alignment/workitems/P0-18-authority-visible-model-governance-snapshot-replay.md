# P0-18 Authority Visible Model Governance Snapshot Replay

Date: 2026-06-07

## Goal

Extend the active governance snapshot lane with authority-resolved visible-model
allow/deny evidence.

This item stays in the P0 low-risk lane: it exports Java neutral contracts and
replays them in Python without changing production engine behavior and without
touching Odoo business models.

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

- Resolver-derived visible model allow:
  - `authority-visible-model-allow-compiles`
  - The compiler runs the one-shot authority-resolution path with no explicit
    `bindings` option.
  - The returned `ModelBinding` is forwarded into the semantic query boundary.
- Resolver-derived visible model deny:
  - `authority-visible-model-deny-missing-binding-fails-closed`
  - The resolver omits the requested model binding.
  - Java and Python fail closed with
    `compose-authority-resolve/model-binding-missing` at `authority-resolve`.

## Python Gap Decision

Python already exposes the one-shot compile path through
`compile_plan_to_sql(..., bindings=None)`, which calls
`resolve_authority_for_plan`. P0-18 records Java parity evidence for the path
instead of introducing new production logic.

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
- Full baseline:
  `.venv/bin/python -m pytest -q`

## Current Verification

Passed:

- Java exporter:
  `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`
- Python replay plus manifest:
  `6 passed in 0.53s`
- Scoped ruff:
  `All checks passed!`
- Full Python pytest:
  `4049 passed, 232 skipped, 43 warnings in 17.65s`

## Follow-Ups

- Add cross-model calculated-field governance refusal snapshots.
- Add sanitized error payload snapshots that prove physical-column details do
  not leak.
- Keep aggregate-join governance as P2 with the aggregate-join design line.
