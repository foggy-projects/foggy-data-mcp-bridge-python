---
doc_role: version-readme
doc_purpose: 记录 Python engine v1.12 针对 Java stable relation runtime parity 的补齐范围、证据和边界
status: signed-off
---

# Python Engine v1.12

## Document Purpose

- doc_type: version-readme
- intended_for: root-controller / python-engine-agent / reviewer
- purpose: 跟踪 v1.11 之后继续补齐 Java/Python runtime parity 的最小版本范围。

## Scope

v1.12 的目标是补齐 v1.11 签收后最明确的 runtime gap：stable relation S7e/S7f outer aggregate / outer window。

本版本不改变 public DSL，不把 compose_script 暴露为 raw SQL escape hatch，不扩大 Pivot 运行时能力。所有 runtime 扩展必须保持 Java S7e/S7f 的 fail-closed 口径。

## Current Status

| Phase | Scope | Status | Notes |
|---|---|---|---|
| P1 stable relation outer query runtime | S7e outer aggregate + S7f outer window internal compiler | signed-off | Internal API only; no public DSL change. |
| P2 cross-dialect oracle refresh | SQLite runtime + dialect marker/refusal evidence | signed-off | SQLite runtime oracle plus dialect fail-closed/marker evidence. |
| P3 version signoff | v1.12 acceptance closeout | signed-off | Full regression passed. |

## Runtime Boundary

Implemented:

- Outer aggregate over `CompiledRelation`.
- Outer window over `CompiledRelation`.
- CTE hoisting for wrappable relations.
- SQL Server `;WITH` marker generation without `FROM (WITH`.
- MySQL 5.7 fail-closed for window and CTE relation wrapping.
- Reference policy validation for `readable`, `groupable`, `aggregatable`, `windowable`, and `orderable`.

Still not included:

- New public query_model / compose_script DSL shape.
- Stable relation join / union as a relation source.
- Arbitrary SQL frame parsing beyond the restricted frame string accepted by S7f.
- Pivot tree+cascade, outer Pivot cache, or SQL Server cascade oracle parity.

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- acceptance_record: docs/v1.12/acceptance/version-signoff.md
- blocking_items: none
- follow_up_required: yes
