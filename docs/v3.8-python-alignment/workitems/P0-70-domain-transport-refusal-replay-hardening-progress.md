# P0-70 Domain Transport Refusal Replay Hardening Progress

## Document Purpose

- doc_type: progress
- intended_for: execution-agent, reviewer
- purpose: Record execution, tests, and closure status for P0-70.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete

## Development Progress

- Added an explicit `DOMAIN_TRANSPORT_BOUNDARY_CASE_IDS` list to the Java
  Pivot/domain snapshot replay.
- Added a fixture-presence test so large-domain and refusal/gap cases cannot be
  removed silently from `java_pivot_domain_snapshot_parity.json`.
- Added parameterized replay for the four boundary cases:
  `domain-sqlite-large-501-transport`,
  `domain-sqlite-python-bind-limit-gap`,
  `domain-empty-columns-refused`, and
  `domain-mysql57-derived-table-java-only-gap`.
- Kept renderer/runtime behavior unchanged; this is replay hardening only.

Touched code paths:

- `tests/integration/test_java_pivot_domain_snapshot_parity.py`
- `docs/v3.8-python-alignment/workitems/P0-70-domain-transport-refusal-replay-hardening.md`
- `docs/v3.8-python-alignment/workitems/P0-70-domain-transport-refusal-replay-hardening-progress.md`
- `docs/v3.8-python-alignment/README.md`
- `docs/v3.8-python-alignment/P0-python-alignment-upgrade-plan.md`

## Testing Progress

| Command | Status | Notes |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_domain_transport.py tests/integration/test_java_snapshot_parity_manifest.py -q` | pass | `41 passed`; covers Java snapshot replay, renderer unit/oracle coverage, and manifest. |
| `.venv/bin/ruff check tests/integration/test_java_pivot_domain_snapshot_parity.py` | pass | Replay file remains lint-clean. |

## Experience Progress

experience: N/A

Reason: P0-70 is backend engine/test evidence. It changes no UI, page,
workflow, form, or manual interaction surface.

## Execution Check-In

Completed work summary:

- Python now names and replays the Java-exported domain transport boundary
  cases directly, including SQLite 501 transport, SQLite 1000-bind fail-closed,
  empty-column fail-closed, and MySQL 5.7 Java-only derived-table gap.

Self-check checklist:

- Scope implemented as intended: yes.
- Non-goals avoided: yes; no production domain transport behavior changed.
- Code paths updated are listed: yes.
- Basic self-review completed: yes.
- Test status recorded: yes.
- Docs and follow-up items recorded: yes.
- Self-check conclusion: self-check-only, no formal quality gate required for
  this bounded replay hardening.

Remaining risks:

- Python still intentionally refuses MySQL 5.7 domain transport while Java can
  render a derived-table strategy.
- Python's SQLite bind guard remains stricter than Java's current guard; the
  gap is documented and replayed, not closed.
- Live DB result parity for domain transport remains future work.
