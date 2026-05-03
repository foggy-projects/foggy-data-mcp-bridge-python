---
doc_role: version_readme
doc_purpose: Record the Python engine v1.15 Java/Python parity baseline after Pivot, timeWindow, CALCULATE, governance, and stable relation evidence refresh.
version: v1.15
target: java-python-engine-parity-baseline
status: signed-off
created_at: 2026-05-03
---

# v1.15 - Java/Python Engine Parity Baseline

## Document Purpose

- doc_type: version-readme
- status: signed-off
- intended_for: root-controller / signoff-owner / python-engine-agent / java-engine-agent
- purpose: 汇总 Python engine 当前与 Java engine 已签收范围的功能对齐、测试证据对齐和剩余测试缺口。

## Scope

v1.15 是证据收口版本，不新增运行时代码，不改变 public DSL，不声明 MDX 兼容。

本版本复盘以下已签收来源：

- Java Pivot Engine 9.1.0 RC2 accepted-with-risks boundary。
- Java 9.2.0 follow-up roadmap。
- Python Pivot v1.9 / v1.10 signoff。
- Python engine v1.11 CALCULATE / timeWindow / governance signoff。
- Python stable relation runtime v1.12 / v1.13 / v1.14 signoff。

## Current Decision

Python engine 与 Java engine 在当前已签收的 public/runtime 能力上可以标记为 **functionally aligned with accepted risks**。

这里的对齐不是“所有候选能力均实现”，而是：

- Java 已开放且 Python 也开放的能力：有 Python oracle 或回归证据。
- Java 明确 fail-closed / deferred 的能力：Python 保持相同拒绝或延期口径。
- Java 仍是 9.2.0 规划项的能力：Python 不提前声明已支持。

## Capability Summary

| Area | Python Status | Java Reference | Test / Evidence Status |
|---|---|---|---|
| base `query_model` lifecycle and governance | aligned | Java queryModel lifecycle / systemSlice / deniedColumns boundary | Python v1.11 governance matrix accepted. |
| restricted `CALCULATE(SUM(metric), REMOVE(dim))` | aligned with MySQL profile note | Java CALCULATE restricted subset | SQLite/MySQL8/PostgreSQL oracle covered; conservative MySQL remains fail-closed. |
| `timeWindow` | aligned | Java timeWindow accepted subset | SQLite/MySQL8/PostgreSQL/SQL Server evidence refreshed in v1.11. |
| Pivot flat/grid baseline | aligned | Java Pivot 9.0/9.1 baseline | SQLite/MySQL8/PostgreSQL oracle covered before v1.9 signoff. |
| Pivot Stage 5A DomainTransport | aligned for SQLite/MySQL8/PostgreSQL; MySQL5.7 refused | Java 9.1 B2 accepted-with-risks | Python v1.9 real DB matrix and v1.10 MySQL5.7 refusal evidence. |
| Pivot Stage 5B rows two-level cascade | aligned for SQLite/MySQL8/PostgreSQL | Java 9.1 C2 accepted-with-risks | Python v1.9 oracle parity and v1.10 cascade totals follow-up. |
| Pivot SQL Server cascade | aligned as refusal | Java 9.1/9.2 deferred/refused | Python v1.10 SQL Server refusal tests; no oracle parity claimed. |
| Pivot MySQL 5.7 cascade / large-domain support | aligned as refusal | Java 9.2 follow-up / guarded fallback | Python v1.10 explicit refusal tests. |
| Pivot tree+cascade | aligned as deferred/refused | Java 9.2 follow-up | Python v1.10 semantic review and runtime refusal. |
| outer Pivot cache | aligned as deferred | Java 9.2 follow-up | Python v1.10 feasibility only; no runtime cache. |
| stable relation outer aggregate/window | Python evidence now stronger | Java stable relation runtime reference | Python v1.12-v1.14 covers SQLite/MySQL8/PostgreSQL/SQL Server live oracle. |
| CTE / compose boundary | aligned for accepted runtime paths | Java CTE/compose tool separation | Python v1.11 governance and compose acceptance; no raw queryModel lifecycle bypass. |

## Documents

| Document | Purpose |
|---|---|
| `coverage/java-python-test-parity-coverage-audit.md` | 测试证据与缺口逐项复盘。 |
| `acceptance/java-python-engine-parity-baseline.md` | v1.15 总签收记录。 |

## Remaining Follow-Ups

这些不是当前对齐阻断项，但后续如果产品要扩大支持范围，需要补实现和 oracle：

- SQL Server Pivot cascade oracle and renderer support.
- MySQL 5.7 live evidence or formally dropped support decision.
- tree+cascade semantic specification and oracle matrix.
- outer Pivot cache key / invalidation / permission safety tests.
- Stable relation join / union as source, if it becomes a public or internal runtime requirement.
- CALCULATE SQL Server real DB oracle, if SQL Server CALCULATE becomes an explicit public parity claim beyond current timeWindow and stable-relation evidence.

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_at: 2026-05-03
- acceptance_record: `docs/v1.15/acceptance/java-python-engine-parity-baseline.md`
- coverage_record: `docs/v1.15/coverage/java-python-test-parity-coverage-audit.md`
- blocking_items: none
- follow_up_required: yes
