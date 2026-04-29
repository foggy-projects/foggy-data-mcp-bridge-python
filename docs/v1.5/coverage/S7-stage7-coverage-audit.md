---
audit_scope: feature
audit_mode: pre-acceptance-check
version: post-v1.5 follow-up
target: S7-stable-relation-runtime-chain
status: reviewed
conclusion: ready-for-acceptance
reviewed_by: root-controller
reviewed_at: 2026-04-29
follow_up_required: no
---

# Test Coverage Audit

## Background

本审计对象是 S7 stable relation runtime chain。该链路把 `timeWindow` / CTE-heavy `QueryPlan` 的结果稳定为 `CompiledRelation`，再在 Java 运行时开放外层 read-only、aggregate、window 查询能力。Python 当前只消费 Java snapshot 并 mirror schema / capability / error constants，不实现 runtime outer query。

审计重点是证据覆盖，而不是代码行覆盖率：确认 CTE wrapping、SQL Server hoisting、MySQL 5.7 fail-closed、timeWindow 输出 schema 稳定、outer aggregate/window 的引用策略和非法场景都有可复核测试或 snapshot 证据。

## Audit Basis

| 类型 | 路径 / 证据 |
|---|---|
| execution plan | `docs/v1.5/P2-post-v1.5-followup-execution-plan.md` |
| runtime contract | `docs/v1.5/S7b-stage7-runtime-contract-plan.md` |
| implementation quality | `docs/v1.5/quality/S7-stage7-implementation-quality.md` |
| S7a preflight | `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md` |
| S7f preflight | `docs/v1.5/S7f-outer-window-contract-preflight.md` |
| Java progress | `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7a-stable-relation-contract-progress.md`, `P2-S7c-compile-to-relation-progress.md`, `P2-S7d-relation-as-source-readonly-progress.md`, `P2-S7e-outer-aggregate-progress.md`, `P2-S7f-outer-window-progress.md` |
| Java commits | `b248404 feat(compose): support relation outer window`; `9a5ad62 fix(compose): validate relation window frame clauses` |
| Python commit | `39b1db4 feat(compose): mirror S7f relation window contract` |
| Java test evidence | S7f reported 2038 passed; quality follow-up focused suite -> 3 Surefire lanes, each 132 passed |
| Python test evidence | focused S7f mirror -> 120 passed; full regression -> 3468 passed |

## Coverage Matrix

| Item | Risk | Unit Test | Integration Test | E2E Test | Playwright Test | Manual Evidence | Evidence Path | Coverage |
|---|---|---|---|---|---|---|---|---|
| S7A1 `CompiledRelation` carries stable SQL, params, output schema, datasource, dialect, capabilities | critical | yes | - | - | - | snapshot | Java `StableRelationSnapshotTest`; Python `test_stable_relation_snapshot.py` | covered |
| S7A2 `ColumnSpec` metadata does not alter equality / hash behavior | critical | yes | - | - | - | - | Java `ColumnSpecMetadataTest`; Python `test_column_spec_metadata.py` | covered |
| S7A3 `timeWindow` derived columns expose stable semantic metadata and reference policy | critical | yes | - | - | - | snapshot | Java stable relation snapshot consumed by Python; S7a contract docs | covered |
| S7A4 SQL Server relation wrapping never emits `FROM (WITH` and uses hoisted CTE where required | critical | yes | - | - | - | snapshot | Java S7a/S7e/S7f snapshot tests; Python snapshot consumers assert forbidden markers | covered |
| S7A5 MySQL 5.7 + inner CTE fails closed instead of generating invalid SQL | critical | yes | - | - | - | snapshot | Java relation snapshot tests; Python S7e/S7f snapshot consumer cases | covered |
| S7B1 S7 object model and string constants are frozen and mirrored 1:1 | major | yes | - | - | - | snapshot | Python S7a/S7b snapshot consumer tests; `S7b-stage7-runtime-contract-plan.md` | covered |
| S7C1 Java `compileToRelation(plan, context, opts)` handles supported plan shapes and preserves capabilities | critical | yes | - | - | - | - | Java `ComposeRelationCompilerTest` | covered |
| S7D1 relation-as-source read-only outer query validates referenced columns and emits stable output schema | critical | yes | - | - | - | - | Java `RelationOuterQueryBuilderTest` S7d cases | covered |
| S7D2 raw filter / order / limit remain constrained by declared relation schema and reference policy | critical | yes | - | - | - | - | Java `RelationOuterQueryBuilderTest`; S7d progress doc | covered |
| S7E1 outer aggregate opens only for wrappable relations and validates `AGGREGATABLE` policy | critical | yes | - | - | - | snapshot | Java S7e tests and `_stable_relation_outer_aggregate_snapshot.json`; Python S7e consumer tests | covered |
| S7E2 ratio columns are rejected for outer aggregate | critical | yes | - | - | - | snapshot | Java S7e rejection case; Python snapshot consumer `outer-sum-ratio-rejected-mysql8` | covered |
| S7E3 SQL Server outer aggregate with inner CTE uses hoisted CTE | critical | yes | - | - | - | snapshot | Java/Python S7e snapshot case `outer-sum-hoisted-sqlserver` | covered |
| S7F1 outer window opens for MySQL8/Postgres/SQLite/SQL Server and remains closed for MySQL 5.7 | critical | yes | - | - | - | snapshot | Java S7f tests; Python S7f capability and snapshot consumer tests | covered |
| S7F2 window inputs require `WINDOWABLE`; ratio/timeWindow-derived ratio columns remain rejected | critical | yes | - | - | - | snapshot | Java `RelationOuterQueryBuilderTest`; Python S7f snapshot consumer | covered |
| S7F3 restricted window parser rejects unsupported functions, unsafe raw SQL, bad aliases, bad partitions, and unsupported frame clauses | critical | yes | - | - | - | - | Java `WindowSelectParser` / `RelationOuterQueryBuilderTest`; quality follow-up commit `9a5ad62` | covered |
| S7F4 outer window output schema preserves lineage and stable value meaning | major | yes | - | - | - | snapshot | Java S7f snapshot; Python S7f snapshot consumer | covered |
| S7X1 `timeWindow + calculatedFields` post-window/post-agg channel remains closed; second-stage logic moves to relation layer | critical | yes | - | - | - | docs | Existing timeWindow calculatedFields tests plus S7b/S7f non-goals | covered |
| S7X2 Python runtime does not prematurely implement outer aggregate/window before Java runtime contract is accepted | major | yes | - | - | - | docs | Python relation model tests and mirror-only docs | covered |

## Evidence Summary

- Java S7f runtime implementation: `b248404 feat(compose): support relation outer window`
- Java S7f quality follow-up: `9a5ad62 fix(compose): validate relation window frame clauses`
- Java reported S7f regression: 2038 tests, 0 failures, 0 errors.
- Java quality follow-up verification: `RelationOuterQueryBuilderTest`, `StableRelationOuterWindowSnapshotTest`, `StableRelationOuterAggregateSnapshotTest`, `StableRelationSnapshotTest`, `RelationModelTest`, `ComposeRelationCompilerTest`, `ComposeCompileErrorCodesTest`, `ColumnSpecMetadataTest` -> 3 Surefire lanes, each 132 passed.
- Python S7f mirror implementation: `39b1db4 feat(compose): mirror S7f relation window contract`.
- Python focused verification: `pytest tests/compose/schema/test_column_spec_metadata.py tests/compose/relation tests/compose/compilation/test_error_codes.py -q` -> 120 passed.
- Python full regression: `pytest -q` -> 3468 passed.
- Quality gate: `docs/v1.5/quality/S7-stage7-implementation-quality.md` -> `ready-for-coverage-audit`.

## Gaps

- No blocking evidence gaps for S7 acceptance.
- Non-blocking: Python remains mirror-only for runtime outer aggregate/window. This matches the agreed contract and is not a missing test.
- Non-blocking: relation join / union and in-memory post-processing are intentionally out of S7 scope.
- Non-blocking: normalized SQL token-by-token diff for architecturally different multi-CTE SQL remains deferred; current S7 evidence relies on structured snapshots, forbidden markers, capability parity, and focused Java runtime tests.

## Recommended Next Skills

- `foggy-acceptance-signoff`: proceed now for feature-level S7 signoff.
- `integration-test`: not required before S7 signoff; runtime SQL Server / MySQL 5.7 dialect risks are already covered by Java runtime tests and Python snapshot consumers for this contract level.
- `plan-evaluator`: optional only if S8 relation composition is reconsidered later.

## Conclusion

- conclusion: `ready-for-acceptance`
- can_enter_acceptance: yes
- follow_up_required: no

判定依据：S7a-S7f 的核心 requirement 均有 Java runtime test、Java snapshot、Python snapshot consumer、Python model parity test 或文档化非目标承接；CTE 与 timeWindow schema 稳定相关的高风险项均已覆盖，无阻断缺口。
