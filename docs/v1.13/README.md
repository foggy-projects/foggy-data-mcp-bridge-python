---
doc_role: version-readme
doc_purpose: 记录 Python engine v1.13 对 stable relation outer query 的三库运行时 oracle 证据补强
status: signed-off
---

# Python Engine v1.13

## Document Purpose

- doc_type: version-readme
- intended_for: root-controller / python-engine-agent / reviewer
- purpose: 跟踪 v1.12 stable relation outer runtime 在真实 SQLite / MySQL8 / PostgreSQL 上的执行级 parity 补强。

## Scope

v1.13 不新增 public DSL，不改变 `query_model` / `pivot` / `compose_script` 入口形态。

本版本只补齐 v1.12 签收时留下的最大证据缺口：stable relation S7e/S7f outer aggregate / outer window 在 MySQL8 与 PostgreSQL 上的真实执行 oracle parity。

## Current Status

| Phase | Scope | Status | Notes |
|---|---|---|---|
| P1 real DB oracle matrix | SQLite / MySQL8 / PostgreSQL 真实执行 | signed-off | 12/12 passed, 0 skipped. |
| P2 version signoff | v1.13 acceptance closeout | signed-off | Full regression passed. |

## Runtime Boundary

Covered by v1.13:

- Outer aggregate over inline `CompiledRelation`.
- Outer aggregate over relation with hoisted CTE and parameter preservation.
- Outer rank over orderable derived ratio.
- Outer moving average over windowable measure.
- SQLite / MySQL8 / PostgreSQL execution result equality against handwritten SQL oracle.

Still not included:

- Public DSL changes.
- SQL Server live execution oracle.
- Stable relation join / union as source.
- Pivot tree+cascade, outer Pivot cache, or public CELL_AT/AXIS_MEMBER operators.

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- acceptance_record: docs/v1.13/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
