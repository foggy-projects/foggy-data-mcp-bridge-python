# P0 Java/Python Engine Parity Execution Plan

## 文档作用

- doc_type: implementation-plan
- status: draft-plan
- intended_for: root-controller / python-engine-agent / reviewer / signoff-owner
- purpose: 将 v1.11 Java/Python engine parity audit 拆成可执行、可评审、可独立签收的阶段。

## Principles

- 不改变 public DSL，除非另有产品需求。
- 先做 evidence refresh，再做 runtime change。
- Java runtime parity、Python contract mirror、accepted-refusal 必须分开标注。
- 不用历史迁移报告替代当前版本签收证据。
- 每个阶段完成后必须补 quality、coverage、acceptance。

## Phase P1 - CALCULATE / Formula Parity

Priority: P0.

Status: accepted-with-profile-note.

Why:

- `query_model_v3.md` 已公开受限 `CALCULATE` 用法。
- 近期本地曾出现 `CALCULATE_WINDOW_UNSUPPORTED` 相关失败，说明该路径正在活跃变化。
- CALCULATE 影响普通 query_model，不应被 Pivot 签收掩盖。

Scope:

- `CALCULATE(SUM(metric), REMOVE(groupByDim...))`。
- grouped aggregate window dialect capability。
- unsupported expressions fail-closed。
- formula compiler / field validator / alias projection interaction。

Required evidence:

- SQLite oracle.
- MySQL8 oracle.
- PostgreSQL oracle.
- unsupported dialect refusal if applicable.
- prompt/schema contract check.

Deliverables:

- `docs/v1.11/acceptance/calculate-formula-parity-acceptance.md`
- `docs/v1.11/coverage/calculate-formula-parity-coverage-audit.md`
- `docs/v1.11/quality/calculate-formula-parity-quality.md`

Closeout:

- SQLite/MySQL8/PostgreSQL oracle parity passed with 0 skips.
- Conservative base `mysql` dialect remains fail-closed; MySQL 8 uses explicit `MySql8Dialect`.

## Phase P2 - timeWindow Current Evidence Refresh

Priority: P1.

Status: accepted.

Scope:

- rolling 7/30/90.
- cumulative.
- yoy/mom/wow.
- timeWindow + scalar calculatedFields.
- timeWindow + pivot rejection.

Required evidence:

- Re-run existing tests on current main.
- SQLite/MySQL8/Postgres matrix.
- SQL Server status: oracle, refusal, or blocked.
- Check historical Java/Python alias projection note and decide whether it still applies.

Deliverables:

- `docs/v1.11/acceptance/timewindow-current-parity-acceptance.md`
- `docs/v1.11/coverage/timewindow-current-parity-coverage-audit.md`
- `docs/v1.11/quality/timewindow-current-parity-quality.md`

Closeout:

- Current main rerun passed: 111 timeWindow / Java alignment / real DB matrix tests.
- `timeWindow + pivot` fail-closed confirmation passed.

## Phase P3 - Compose / Stable Relation Runtime Boundary

Priority: P1.

Status: accepted-with-runtime-boundary.

Scope:

- basic CTE compose runtime.
- `compose_script` MCP exposure.
- stable relation model / snapshot parity.
- outer aggregate / outer window: runtime parity or contract mirror only.
- dialect fallback/refusal for SQL Server and MySQL 5.7.

Required evidence:

- targeted compose tests.
- snapshot consumer tests.
- at least one end-to-end compose_script path if MCP tool is public.
- explicit runtime-vs-mirror matrix.

Deliverables:

- `docs/v1.11/acceptance/compose-stable-relation-boundary-acceptance.md`
- `docs/v1.11/coverage/compose-stable-relation-boundary-coverage-audit.md`
- `docs/v1.11/quality/compose-stable-relation-boundary-quality.md`

Closeout:

- `tests/compose` passed with 1146 tests.
- MCP `compose_script` binding passed with 10 tests.
- Stable relation S7a/S7e/S7f snapshot consumer tests passed with 70 tests.
- Basic compose runtime is accepted; stable relation outer aggregate/window stays `contract-mirror-only`.

## Phase P4 - Governance Cross-Path Matrix

Priority: P1.

Status: accepted.

Scope:

- `systemSlice`
- `deniedColumns`
- fieldAccess visible filtering
- masking
- query_model base path
- timeWindow path
- pivot path
- compose path

Required evidence:

- Tests proving governance is applied before SQL where required.
- Tests proving response filtering/masking is applied after SQL where required.
- Tests proving denied columns cannot leak through derived outputs, DomainTransport, cascade, or compose relation wrapping.

Deliverables:

- `docs/v1.11/acceptance/governance-cross-path-acceptance.md`
- `docs/v1.11/coverage/governance-cross-path-coverage-audit.md`
- `docs/v1.11/quality/governance-cross-path-quality.md`

Closeout:

- Base/timeWindow/pivot/compose governance target matrix passed with 215 tests.
- MCP router plus compose authority/security matrix passed with 120 tests.
- P4 added direct timeWindow systemSlice, deniedColumns, and masking tests.

## Phase P5 - Version Signoff

Priority: P2.

Scope:

- Consolidate P1-P4.
- Update `docs/v1.11/README.md`.
- Produce version-level signoff.

Acceptance decision options:

- `accepted`: only if all P1-P4 have current evidence and no open runtime-vs-contract ambiguity.
- `accepted-with-risks`: if stable relation remains contract mirror or some dialects remain accepted-refusal.
- `blocked`: if public prompt claims runtime support that tests do not prove.

Deliverables:

- `docs/v1.11/acceptance/version-signoff.md`

## Current Recommendation

Start with P5 version signoff.

Do not implement tree+cascade, outer Pivot cache, or stable relation runtime expansion until v1.11 signoff is recorded and a separate product requirement approves runtime expansion.
