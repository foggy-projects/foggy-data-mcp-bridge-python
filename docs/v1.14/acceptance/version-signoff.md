---
acceptance_scope: version
version: v1.14
target: stable-relation-outer-sqlserver-live-parity
doc_role: acceptance-record
doc_purpose: 记录 Python engine v1.14 stable relation outer query SQL Server live runtime parity 的版本级正式验收结论
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
- purpose: 记录 v1.14 对 SQL Server stable relation outer runtime 证据缺口的收口结论。

## Scope

v1.14 只覆盖 stable relation S7e/S7f outer query SQL Server live parity：

- SQL Server outer aggregate oracle.
- SQL Server outer window oracle.
- SQL Server `;WITH` CTE hoist runtime evidence.
- Existing SQLite / MySQL8 / PostgreSQL matrix remains covered in the same test.

不包含：

- public DSL changes.
- Stable relation join / union as source.
- Pivot tree+cascade / outer Pivot cache / CELL_AT/AXIS_MEMBER.
- Pivot SQL Server cascade oracle.

## Acceptance Basis

- `docs/v1.14/README.md`
- `docs/v1.14/acceptance/stable-relation-outer-sqlserver-acceptance.md`
- `docs/v1.14/coverage/stable-relation-outer-sqlserver-coverage-audit.md`
- `docs/v1.14/quality/stable-relation-outer-sqlserver-quality.md`

## Evidence

```powershell
pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 16 passed in 1.61s

pytest tests/compose/relation/test_relation_outer_query_runtime.py tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 25 passed in 1.30s

pytest -q
# 3977 passed in 13.57s
```

## Risks / Open Items

| Item | Status | Impact | Follow-Up |
|---|---|---|---|
| Public DSL usage | not applicable | Stable relation outer compiler remains internal. | Separate product requirement required before exposure. |
| Pivot deferred items | unchanged | Not part of v1.14. | Continue tracking under Pivot follow-up docs. |
| Relation join / union source | unchanged | Not part of S7e/S7f outer query. | Separate stable relation requirement required. |

## Final Decision

v1.14 is `accepted`.

Stable relation S7e/S7f outer aggregate/window now has live runtime oracle evidence across SQLite, MySQL8, PostgreSQL, and SQL Server. The remaining Java/Python gaps are no longer in this stable relation outer-query slice; they are separate, explicitly deferred product areas.
