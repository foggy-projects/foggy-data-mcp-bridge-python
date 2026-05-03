---
acceptance_scope: version
version: v1.12
target: stable-relation-runtime-parity
doc_role: acceptance-record
doc_purpose: 记录 Python engine v1.12 stable relation runtime parity 的版本级正式验收结论
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-05-03
blocking_items: []
follow_up_required: yes
evidence_count: 3
---

# Version Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / root-controller
- purpose: 记录 v1.12 对 v1.11 之后最大 Java/Python runtime gap 的补齐结论。

## Scope

v1.12 只覆盖 stable relation S7e/S7f outer query runtime：

- S7e outer aggregate over `CompiledRelation`.
- S7f outer window over `CompiledRelation`.
- CTE hoist / SQL Server marker / MySQL 5.7 fail-closed behavior.

不包含：

- public DSL changes.
- Pivot tree+cascade / outer Pivot cache / SQL Server cascade oracle.
- stable relation join / union as source.

## Acceptance Basis

- `docs/v1.12/README.md`
- `docs/v1.12/acceptance/stable-relation-outer-runtime-acceptance.md`
- `docs/v1.12/coverage/stable-relation-outer-runtime-coverage-audit.md`
- `docs/v1.12/quality/stable-relation-outer-runtime-quality.md`

## Evidence

```powershell
pytest tests/compose/relation/test_relation_outer_query_runtime.py -q
# 9 passed in 0.06s

pytest tests/compose/relation -q -rs
# 106 passed in 0.15s

pytest -q
# 3961 passed in 12.14s
```

## Risks / Open Items

| Item | Status | Impact | Follow-Up |
|---|---|---|---|
| Live MySQL8/PostgreSQL/SQL Server execution for relation outer query | not claimed | Runtime proof is SQLite oracle plus dialect marker/refusal behavior. | Add live matrix only if product requires relation outer query execution on those DBs. |
| Restricted window frame string | accepted risk | API is internal and validates statement breaks, but frame grammar is not fully structured. | Introduce structured frame object if this becomes public-facing. |
| Pivot deferred items | unchanged | Not part of v1.12. | Continue tracking under Pivot follow-up docs. |

## Final Decision

v1.12 is `accepted-with-risks`.

The practical Java/Python runtime gap identified in v1.11, stable relation S7e/S7f outer aggregate/window execution, now has a Python internal runtime compiler and SQLite oracle evidence. Unsupported or unproven dialect paths remain explicit fail-closed or marker-only; no public DSL behavior changed.
