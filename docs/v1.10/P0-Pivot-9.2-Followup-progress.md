# P0 Pivot 9.2 Follow-Up Progress

## 文档作用

- doc_type: progress-template
- status: active
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 作为 Python Pivot 9.2 follow-up 的阶段性进度回写模板。

## Basic Info

- version: v1.10
- target: Python Pivot 9.2 Follow-Up
- upstream_requirement: `docs/v1.10/P0-Pivot-9.2-Followup-Requirement.md`
- implementation_plan: `docs/v1.10/P0-Pivot-9.2-Followup-Implementation-Plan.md`
- current_status: p1-cascade-totals-accepted
- last_updated: 2026-05-03

## Phase Progress

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| P0 | planning docs | accepted | `docs/v1.10` planning package reviewed |
| P1 | cascade subtotal/grandTotal | accepted | `acceptance/pivot-9.2-cascade-totals-acceptance.md` |
| P2 | SQL Server cascade evidence | not-started | N/A |
| P3 | MySQL 5.7 evidence | not-started | N/A |
| P4 | tree + cascade semantic review | deferred | N/A |
| P5 | outer Pivot cache feasibility | deferred | N/A |
| P6 | production telemetry examples | not-started | N/A |

## Implementation Self-Check Template

When an implementation phase completes, fill this section before requesting review:

- [x] Requirement scope closed.
- [x] No public DSL change unless separately accepted.
- [x] Unsupported shapes still fail closed.
- [x] No cascade memory fallback introduced without oracle coverage.
- [x] QueryModel lifecycle, permissions, systemSlice, deniedColumns, sanitizer preserved.
- [x] No temporary scripts, scratch files, or unrelated changes included.
- [x] Tests and docs updated.
- self_check_conclusion: P1 runtime only appends additive totals after staged SQL surviving-domain selection; unsupported totals shapes remain fail-closed.

## Testing Progress Template

| Command | Status | Result / Notes |
|---|---|---|
| `pytest -q` | passed | `3938 passed in 12.09s` |
| targeted unit tests | passed | `39 passed in 1.59s` |
| SQLite oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py` |
| MySQL8 oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py`, 0 skipped in targeted run |
| PostgreSQL oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py`, 0 skipped in targeted run |
| SQL Server oracle/refusal | not-run | TBD |
| MySQL 5.7 oracle/refusal | not-run | TBD |

## Acceptance Criteria Mapping

| Requirement | Status | Evidence |
|---|---|---|
| cascade totals have oracle or remain rejected | accepted | P1 acceptance + coverage docs |
| SQL Server has parity/refusal evidence | pending | TBD |
| MySQL 5.7 has live/refusal evidence | pending | TBD |
| tree+cascade remains rejected until semantic signoff | pending | TBD |
| telemetry examples do not leak sensitive details | pending | TBD |
| schema/prompt match runtime | pending | TBD |

## Blockers

| Blocker | Status | Owner | Notes |
|---|---|---|---|
| P2 SQL Server evidence not started | open | python-engine-agent | Next follow-up candidate. |

## Follow-Up

Next recommended action after P1 acceptance:

1. Run final full `pytest -q`.
2. Review and sign off P1 docs.
3. Choose P2 SQL Server evidence or P6 telemetry examples as the next task.
4. Do not start P4 tree+cascade runtime implementation before a separate semantic decision record exists.
