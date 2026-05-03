---
doc_role: version-readme
doc_purpose: 记录 Python engine v1.14 对 stable relation outer query SQL Server live oracle 的补齐范围、证据和边界
status: signed-off
---

# Python Engine v1.14

## Document Purpose

- doc_type: version-readme
- intended_for: root-controller / python-engine-agent / reviewer
- purpose: 跟踪 v1.13 之后继续补齐 stable relation outer query SQL Server live runtime parity 的最小版本范围。

## Scope

v1.14 不新增 public DSL，不改变 `query_model` / `pivot` / `compose_script` 入口形态。

本版本只补齐 v1.13 签收时留下的 stable relation SQL Server live oracle 缺口：S7e outer aggregate / S7f outer window 在 SQL Server 上真实执行，并与手写 SQL oracle 对齐。

## Current Status

| Phase | Scope | Status | Notes |
|---|---|---|---|
| P1 SQL Server live oracle | stable relation outer aggregate/window | signed-off | Matrix expanded to SQLite/MySQL8/PostgreSQL/SQL Server, 16/16 passed, 0 skipped. |
| P2 version signoff | v1.14 acceptance closeout | signed-off | Full regression passed. |

## Runtime Boundary

Covered by v1.14:

- SQL Server outer aggregate over inline `CompiledRelation`.
- SQL Server outer aggregate over hoisted CTE relation using `;WITH`.
- SQL Server outer rank over orderable derived ratio.
- SQL Server outer moving average over windowable measure.
- Four-dialect result equality against handwritten SQL oracle: SQLite / MySQL8 / PostgreSQL / SQL Server.

Still not included:

- Public DSL changes.
- Stable relation join / union as source.
- Pivot tree+cascade, outer Pivot cache, or public CELL_AT/AXIS_MEMBER operators.

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- acceptance_record: docs/v1.14/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
