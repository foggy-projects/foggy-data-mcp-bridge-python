---
acceptance_scope: version
version: v1.13
target: stable-relation-outer-real-db-parity
doc_role: acceptance-record
doc_purpose: 记录 Python engine v1.13 stable relation outer query 三库 runtime parity 的版本级正式验收结论
status: signed-off
decision: accepted
signed_off_by: root-controller
signed_off_at: 2026-05-03
blocking_items: []
follow_up_required: yes
evidence_count: 4
---

# Version Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / root-controller
- purpose: 记录 v1.13 对 v1.12 accepted risk 的收口结论。

## Scope

v1.13 只覆盖 stable relation S7e/S7f outer query real DB parity：

- SQLite / MySQL8 / PostgreSQL outer aggregate oracle.
- SQLite / MySQL8 / PostgreSQL outer window oracle.
- CTE hoist + params order runtime evidence.

不包含：

- public DSL changes.
- SQL Server live execution.
- Pivot tree+cascade / outer Pivot cache / CELL_AT/AXIS_MEMBER.

## Acceptance Basis

- `docs/v1.13/README.md`
- `docs/v1.13/acceptance/stable-relation-outer-real-db-acceptance.md`
- `docs/v1.13/coverage/stable-relation-outer-real-db-coverage-audit.md`
- `docs/v1.13/quality/stable-relation-outer-real-db-quality.md`

## Evidence

```powershell
pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 12 passed in 0.94s

pytest tests/compose/relation/test_relation_outer_query_runtime.py tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 21 passed in 0.87s

pytest -q
# 3973 passed in 14.17s
```

## Risks / Open Items

| Item | Status | Impact | Follow-Up |
|---|---|---|---|
| SQL Server live relation outer execution | not claimed | No SQL Server oracle evidence in Python. | Add only if SQL Server fixture becomes release requirement. |
| Public DSL usage | not applicable | Stable relation outer compiler remains internal. | Separate product requirement required before exposure. |
| Pivot deferred items | unchanged | Not part of v1.13. | Continue tracking under Pivot follow-up docs. |

## Final Decision

v1.13 is `accepted`.

The v1.12 live MySQL8/PostgreSQL evidence gap is closed for stable relation S7e/S7f outer aggregate/window. Python engine functional parity with the Java stable relation runtime is materially stronger, while unsupported public or SQL Server paths remain explicitly out of scope.
