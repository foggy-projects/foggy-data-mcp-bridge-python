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
- current_status: v1.10-followups-closed
- last_updated: 2026-05-03

## Phase Progress

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| P0 | planning docs | accepted | `docs/v1.10` planning package reviewed |
| P1 | cascade subtotal/grandTotal | accepted | `acceptance/pivot-9.2-cascade-totals-acceptance.md` |
| P2 | SQL Server cascade evidence | accepted-refusal | `acceptance/pivot-9.2-sqlserver-cascade-refusal-acceptance.md` |
| P3 | MySQL 5.7 evidence | accepted-refusal | `acceptance/pivot-9.2-mysql57-refusal-acceptance.md` |
| P4 | tree + cascade semantic review | accepted-deferred | `acceptance/pivot-9.2-tree-cascade-semantic-review.md` |
| P5 | outer Pivot cache feasibility | accepted-deferred | `acceptance/pivot-9.2-outer-cache-feasibility.md` |
| P6 | production telemetry examples | accepted-docs | `operations/pivot-9.2-telemetry-log-query-examples.md` |

## Implementation Self-Check Template

When an implementation phase completes, fill this section before requesting review:

- [x] Requirement scope closed.
- [x] No public DSL change unless separately accepted.
- [x] Unsupported shapes still fail closed.
- [x] No cascade memory fallback introduced without oracle coverage.
- [x] QueryModel lifecycle, permissions, systemSlice, deniedColumns, sanitizer preserved.
- [x] No temporary scripts, scratch files, or unrelated changes included.
- [x] Tests and docs updated.
- self_check_conclusion: P1-P6 are closed for v1.10. P5 is feasibility-only; no outer Pivot cache runtime was added because permission-aware cache key, invalidation, and telemetry evidence are not yet signed.

## Testing Progress Template

| Command | Status | Result / Notes |
|---|---|---|
| `pytest -q` | passed | `3943 passed in 11.79s` |
| targeted unit tests | passed | `39 passed in 1.59s` |
| SQLite oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py` |
| MySQL8 oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py`, 0 skipped in targeted run |
| PostgreSQL oracle | passed | included in `test_pivot_v9_cascade_real_db_matrix.py`, 0 skipped in targeted run |
| SQL Server oracle/refusal | passed | targeted `8 passed in 0.48s`; cascade regression `32 passed in 1.38s`; accepted-refusal, no oracle parity claimed |
| MySQL 5.7 oracle/refusal | passed | targeted `2 passed in 0.25s`; regression `34 passed in 0.28s`; accepted-refusal, no oracle parity claimed |

## Acceptance Criteria Mapping

| Requirement | Status | Evidence |
|---|---|---|
| cascade totals have oracle or remain rejected | accepted | P1 acceptance + coverage docs |
| SQL Server has parity/refusal evidence | accepted-refusal | P2 acceptance + coverage docs |
| MySQL 5.7 has live/refusal evidence | accepted-refusal | P3 acceptance + coverage docs |
| tree+cascade remains rejected until semantic signoff | accepted-deferred | P4 semantic review keeps runtime rejected until a future signed spec exists |
| telemetry examples do not leak sensitive details | accepted-docs | P6 operations guide + quality docs |
| schema/prompt match runtime | accepted-docs | P6 public contract update and `acceptance/pivot-9.2-telemetry-docs-acceptance.md` |

## Blockers

| Blocker | Status | Owner | Notes |
|---|---|---|---|
| Future outer Pivot cache implementation | deferred | performance owner | Requires production latency evidence plus signed permission-aware cache key and invalidation spec. |

## Follow-Up

Next recommended action after v1.10 follow-up closure:

1. Review and sign off P1-P6 docs as the Python Pivot 9.2 follow-up closeout.
2. Do not start tree+cascade runtime implementation before a future semantic spec and oracle matrix are signed.
3. Do not start outer Pivot cache runtime before production telemetry, permission-aware cache key, and invalidation strategy are signed.
