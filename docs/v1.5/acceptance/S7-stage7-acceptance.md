---
acceptance_scope: feature
version: post-v1.5 follow-up
target: S7-stable-relation-runtime-chain
doc_role: acceptance-record
doc_purpose: 说明本文件用于 S7 stable relation runtime chain 的功能级正式验收与签收结论记录
status: signed-off
decision: accepted-with-risks
signed_off_by: root-controller
signed_off_at: 2026-04-29
reviewed_by: N/A
blocking_items: []
follow_up_required: yes
evidence_count: 10
---

# Feature Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: signoff-owner / reviewer / Java contract owner / Python mirror owner
- purpose: 记录 S7 stable relation runtime chain 的正式验收结论、证据摘要和后续边界。

## Background

- Version: post-v1.5 follow-up
- Target: S7-stable-relation-runtime-chain
- Owner: Java runtime owner + Python mirror owner, coordinated by root-controller
- Goal: 把 CTE-heavy / timeWindow-heavy `QueryPlan` 稳定为 `CompiledRelation`，并在 Java runtime 中分阶段开放 relation-as-source、outer aggregate、outer window，同时由 Python 镜像对象模型、能力矩阵、错误码和 snapshot consumer。

S7 的目标不是启动 S8，也不是把 relation 继续 join / union。当前签收结论只覆盖 S7a-S7f：stable relation schema、CTE wrapping contract、Java runtime outer query 能力、Python mirror parity。

## Acceptance Basis

- `docs/v1.5/P2-post-v1.5-followup-execution-plan.md`
- `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md`
- `docs/v1.5/S7b-stage7-runtime-contract-plan.md`
- `docs/v1.5/S7f-outer-window-contract-preflight.md`
- `docs/v1.5/quality/S7-stage7-implementation-quality.md`
- `docs/v1.5/coverage/S7-stage7-coverage-audit.md`
- `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7a-stable-relation-contract-progress.md`
- `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7c-compile-to-relation-progress.md`
- `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7d-relation-as-source-readonly-progress.md`
- `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7e-outer-aggregate-progress.md`
- `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7f-outer-window-progress.md`

## Checklist

- [x] scope 内功能点已全部交付：S7a model、S7b freeze、S7c compileToRelation、S7d read-only outer query、S7e outer aggregate、S7f outer window。
- [x] 原始 acceptance criteria 已逐项覆盖：stable output schema、CTE hoisting、MySQL 5.7 fail-closed、referencePolicy、ratio rejection、frame rejection、Python mirror parity。
- [x] CTE 规则满足签收要求：不得生成 `FROM (WITH`；SQL Server inner CTE 使用 hoisted CTE；不支持 hoist 的方言 fail-closed。
- [x] timeWindow 能力边界满足签收要求：timeWindow 派生列有稳定 schema 含义；二次聚合/二次窗口不回塞 timeWindow calculatedFields 通道，而是通过 relation 外层能力承接。
- [x] 关键测试已通过：Java S7f regression、Java quality follow-up focused suite、Python S7f focused mirror、Python full regression。
- [x] 质量闸门已完成：`ready-for-coverage-audit`，且 frame validation 问题已在 Java `9a5ad62` 修复。
- [x] 覆盖审计已完成：`ready-for-acceptance`，无阻断缺口。
- [x] 体验验证已完成，或明确标记 `N/A`：后端 DSL / SQL engine capability，无 UI。
- [x] 文档、配置、依赖项已闭环：plan / preflight / quality / coverage / acceptance 均已落盘。

## Evidence

- Java runtime commits:
  - `b248404 feat(compose): support relation outer window`
  - `9a5ad62 fix(compose): validate relation window frame clauses`
- Python mirror commit:
  - `39b1db4 feat(compose): mirror S7f relation window contract`
- Quality:
  - `docs/v1.5/quality/S7-stage7-implementation-quality.md`
- Coverage:
  - `docs/v1.5/coverage/S7-stage7-coverage-audit.md`
- Java runtime / snapshot evidence:
  - S7f reported 2038 tests, 0 failures, 0 errors.
  - Quality follow-up focused suite -> 3 Surefire lanes, each 132 passed.
  - S7a/S7e/S7f snapshots cover schema metadata, outer aggregate, outer window, SQL markers, error cases, and dialect capabilities.
- Python mirror evidence:
  - S7f focused mirror -> 120 passed.
  - Full regression -> 3468 passed.
  - Snapshot consumers validate S7a/S7e/S7f Java output without opening Python runtime outer aggregate/window.

## Failed Items

- none

## Risks / Open Items

- accepted risk: Python runtime outer aggregate / outer window remains intentionally unimplemented. Python is mirror-only for S7 runtime capabilities.
- accepted risk: relation join / union, relation composition chaining, and in-memory join / post-processing are not part of S7 and are not started.
- accepted risk: normalized token-by-token golden diff for architecturally different multi-CTE SQL remains deferred. Current acceptance relies on Java runtime tests, structured snapshots, marker assertions, and Python snapshot consumers.
- follow-up focus: continue with CTE and timeWindow capability recap, especially documenting what is aligned, what is explicitly closed, and what is deferred.

## Final Decision

结论：`accepted-with-risks`。

理由：S7a-S7f 的功能范围、CTE contract、timeWindow stable schema 目标、Java runtime 能力、Python mirror parity、质量闸门和覆盖审计均已闭环。遗留项均为已明确的非目标或后续方向，不阻断当前 S7 签收。

## Signoff Marker

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: root-controller
- signed_off_at: 2026-04-29
- acceptance_record: docs/v1.5/acceptance/S7-stage7-acceptance.md
- blocking_items: none
- follow_up_required: yes
