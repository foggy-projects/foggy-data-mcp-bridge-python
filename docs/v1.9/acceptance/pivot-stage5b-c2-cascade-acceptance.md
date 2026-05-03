---
acceptance_scope: feature
version: v1.9
target: pivot-stage5b-c2-cascade
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
reviewed_by: root-controller
blocking_items: []
follow_up_required: yes
evidence_count: 6
doc_role: feature-acceptance
doc_purpose: Record scoped Python Pivot 9.1 Stage 5B C2 cascade signoff.
---

# Feature Acceptance

## Background

Python Pivot v1.9 mirrors the accepted Java Pivot 9.1 execution principles:
correctness-first, LLM-safe behavior, no public Pivot DSL change, and
fail-closed handling when a shape cannot be proven safe. This feature signs off
the scoped Stage 5B C2 subset: rows-axis exactly two-level cascade TopN using
staged SQL for SQLite, MySQL8, and PostgreSQL.

## Acceptance Basis

- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Requirement.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-Implementation-Plan.md`
- `docs/v1.9/P0-Pivot-9.1-Java-Parity-progress.md`
- `docs/v1.9/quality/pivot-stage5b-c2-cascade-implementation-quality.md`
- `docs/v1.9/coverage/pivot-stage5b-c2-cascade-coverage-audit.md`

## Checklist

- [x] Public Pivot DSL remains unchanged.
- [x] Rows-axis exactly two-level cascade TopN is routed to staged SQL.
- [x] Unsupported cascade shapes fail closed with stable `PIVOT_CASCADE_*` errors.
- [x] Cascade requests do not fall back to the existing memory-only path.
- [x] Parent and child domain ranking semantics are covered by tests.
- [x] NULL-safe cascade domain joins are implemented per dialect.
- [x] SQLite, MySQL8, and PostgreSQL real SQL oracle parity is covered with 0 skipped tests.
- [x] Stage 5A domain transport remains covered and non-regressed.
- [x] Full repository regression is clean.
- [x] Quality gate and coverage audit records exist.
- [x] Cascade subtotal/grandTotal rows are not claimed as signed off in P4.

## Evidence

- Quality gate:
  `docs/v1.9/quality/pivot-stage5b-c2-cascade-implementation-quality.md`
- Coverage audit:
  `docs/v1.9/coverage/pivot-stage5b-c2-cascade-coverage-audit.md`
- P4 targeted tests:
  `pytest tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs`
  -> `12 passed, 0 skipped`
- Pivot regression pack:
  `pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_domain_transport.py tests/test_dataset_model/test_pivot_v9_domain_transport_query_model.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs`
  -> `105 passed, 0 skipped`
- Full regression:
  `pytest -q` -> `3928 passed`
- Diff hygiene:
  `git diff --check` -> clean, with Windows CRLF warnings only

## Failed Items

None for the scoped P4 Stage 5B C2 cascade signoff.

## Risks / Open Items

- Cascade subtotal/grandTotal row parity is deferred to Python 9.2.
- SQL Server cascade oracle and MySQL 5.7 live evidence are deferred.
- Tree + cascade and cross-axis cascade remain refused/deferred.
- The repository worktree contains unrelated dirty files outside the scoped
  Pivot P4/P5 changes. Those must not be mixed into the Pivot signoff commit.

## Final Decision

Decision: `accepted-with-risks`.

The scoped Python Pivot 9.1 Stage 5B C2 cascade staged SQL feature is signed
off. The risk is limited to explicitly deferred subtotal/grandTotal and
additional dialect follow-ups; it does not block the scoped P4 feature.

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-05-03
- acceptance_record: docs/v1.9/acceptance/pivot-stage5b-c2-cascade-acceptance.md
- blocking_items: none
- follow_up_required: yes
