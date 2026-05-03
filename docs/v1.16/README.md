---
doc_role: version_readme
doc_purpose: Track confirmation intake for Java/Python parity follow-ups identified after v1.15 baseline signoff.
version: v1.16
target: java-python-parity-followup-confirmation
status: proposed
created_at: 2026-05-03
---

# v1.16 - Java/Python Parity Follow-Up Confirmation

## 文档作用

- doc_type: version-readme
- status: proposed
- intended_for: root-controller / product-owner / python-engine-agent / java-engine-agent
- purpose: 承接 v1.15 parity baseline 复盘后的剩余问题，先逐项确认是否进入后续实现，而不是直接开工。

## Background

v1.15 已签收当前 Java/Python engine parity baseline，结论是 `accepted-with-risks`：

- 已开放能力：Python 与 Java 在当前已签收 public/runtime 范围内功能对齐。
- 未开放能力：保持 fail-closed、accepted-refusal 或 deferred，不用近似实现冒充支持。

v1.16 的目标是把 v1.15 标出的剩余问题放入合适迭代，并逐个完成产品/技术确认。

## Scope

本版本是 intake / confirmation，不包含运行时代码实现。

| Item | Suggested Iteration | Confirmation Status | Runtime Work in v1.16? |
|---|---|---|---|
| CALCULATE SQL Server oracle | v1.16 P1 | pending | no, evidence planning only until confirmed |
| Stable relation join / union as source | v1.16 P2 | pending | no, requirement clarification only |
| Pivot SQL Server cascade oracle | v1.17 P1 | pending | no |
| Pivot MySQL 5.7 live evidence | v1.17 P2 | pending | no |
| tree+cascade semantic spec | v1.18 P1 | pending | no |
| outer Pivot cache feasibility / runtime | v1.19 P1 | pending | no |

## Documents

| Document | Purpose |
|---|---|
| `P0-Java-Python-Parity-Followup-Confirmation.md` | 每个剩余问题的迭代归属、确认问题、测试要求和非目标。 |
| `P0-Java-Python-Parity-Followup-progress.md` | 后续逐项确认和执行状态回写。 |

## Guardrails

- Do not change public DSL without a separate accepted requirement.
- Do not claim support before executable oracle or refusal evidence exists.
- Do not bypass queryModel lifecycle, governance, systemSlice, deniedColumns, sanitizer, or dialect routing.
- Keep Java deferred/refusal boundaries visible; Python must not silently exceed Java's signed semantics.
- Any runtime implementation must go through quality gate, coverage audit, and acceptance signoff.

## Current Decision

v1.16 is ready for item-by-item confirmation. No item is pre-approved for implementation.

## Signoff Marker

- acceptance_status: not-started
- acceptance_decision: pending
- blocking_items: item confirmation pending
- follow_up_required: yes
