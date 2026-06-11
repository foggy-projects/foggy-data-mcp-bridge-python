# P0-71 Domain Transport SQLite Live Result Replay Progress

## Document Purpose

- doc_type: progress
- intended_for: execution-agent, reviewer
- purpose: Record execution, tests, and closure status for P0-71.

Version: v3.8 Python alignment
Priority: P0
Status: coding complete

## Development Progress

- Added Java fixture-driven SQLite live-result replay to
  `tests/integration/test_java_pivot_domain_snapshot_parity.py`.
- Replayed `domain-sqlite-two-field-null-safe` through
  `assemble_domain_transport_sql(...)`, executing the assembled SQL against a
  seeded SQLite table and comparing with independent oracle SQL.
- Replayed `domain-sqlite-large-501-transport` with 501 Java fixture domain
  members, proving assembled CTE transport filters in-domain rows and excludes
  an out-of-domain row.
- Kept production domain transport code unchanged.

Touched code paths:

- `tests/integration/test_java_pivot_domain_snapshot_parity.py`
- `docs/v3.8-python-alignment/workitems/P0-71-domain-transport-sqlite-live-result-replay.md`
- `docs/v3.8-python-alignment/workitems/P0-71-domain-transport-sqlite-live-result-replay-progress.md`
- `docs/v3.8-python-alignment/README.md`
- `docs/v3.8-python-alignment/P0-python-alignment-upgrade-plan.md`

## Testing Progress

| Command | Status | Notes |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/integration/test_java_pivot_domain_snapshot_parity.py tests/test_dataset_model/test_pivot_v9_domain_transport.py tests/integration/test_java_snapshot_parity_manifest.py -q` | pass | `43 passed`; includes Java snapshot replay, Java-fixture-driven SQLite live-result replay, renderer oracle tests, and manifest. |
| `.venv/bin/ruff check tests/integration/test_java_pivot_domain_snapshot_parity.py` | pass | Replay file remains lint-clean. |

## Experience Progress

experience: N/A

Reason: P0-71 is backend engine/test evidence. It changes no UI, page,
workflow, form, or manual interaction surface.

## Execution Check-In

Completed work summary:

- Python now executes Java-exported SQLite domain transport plans against
  SQLite and validates live results against independent oracle SQL for both
  NULL-safe multi-column matching and 501-member CTE transport.

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

- This is SQLite live-result evidence only; external MySQL8/PostgreSQL
  live-result parity remains covered by existing optional real DB tests, not by
  Java fixture replay.
- MySQL 5.7 derived-table transport remains a documented Java-only gap.
- Direct axis-domain API behavior still needs a dedicated snapshot if product
  treats it as a shared contract.
