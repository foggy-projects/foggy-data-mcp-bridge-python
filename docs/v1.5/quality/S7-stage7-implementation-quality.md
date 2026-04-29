---
quality_scope: feature
quality_mode: pre-coverage-audit
version: post-v1.5 follow-up
target: S7-stable-relation-runtime-chain
status: reviewed
decision: ready-for-coverage-audit
reviewed_by: root-controller
reviewed_at: 2026-04-29
follow_up_required: yes
---

# Implementation Quality Gate

## Background

本质量门覆盖 Stage 7 的 stable relation runtime chain：S7a stable relation model、S7b contract freeze、S7c `compileToRelation` runtime entry、S7d relation-as-source read-only query、S7e outer aggregate、S7f outer window。

Stage 7 的核心设计是把复杂二次查询建模为 `QueryPlan -> CompiledRelation -> outer query`，而不是把二次聚合或二次窗口继续塞回同一层 timeWindow DSL。Java 是 runtime contract owner，Python 当前只作为 model mirror 和 Java snapshot consumer，不实现 runtime outer aggregate / outer window。

## Check Basis

| 类型 | 路径 / 证据 |
|---|---|
| execution plan | `docs/v1.5/P2-post-v1.5-followup-execution-plan.md` |
| runtime contract plan | `docs/v1.5/S7b-stage7-runtime-contract-plan.md` |
| S7a preflight | `docs/v1.5/S7a-plan-stable-view-relation-contract-preflight.md` |
| S7f preflight | `docs/v1.5/S7f-outer-window-contract-preflight.md` |
| Java S7a progress | `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7a-stable-relation-contract-progress.md` |
| Java S7c-S7f progress | `foggy-data-mcp-bridge-wt-dev-compose/docs/8.5.0.beta/P2-S7c-compile-to-relation-progress.md`, `P2-S7d-relation-as-source-readonly-progress.md`, `P2-S7e-outer-aggregate-progress.md`, `P2-S7f-outer-window-progress.md` |
| Java S7f runtime commit | `b248404 feat(compose): support relation outer window` |
| Java quality follow-up commit | `9a5ad62 fix(compose): validate relation window frame clauses` |
| Python S7f mirror commit | `39b1db4 feat(compose): mirror S7f relation window contract` |
| Java S7f reported regression | 2038 tests, 0 failures, 0 errors |
| Java quality follow-up verification | `RelationOuterQueryBuilderTest`, `StableRelationOuterWindowSnapshotTest`, `StableRelationOuterAggregateSnapshotTest`, `StableRelationSnapshotTest`, `RelationModelTest`, `ComposeRelationCompilerTest`, `ComposeCompileErrorCodesTest`, `ColumnSpecMetadataTest` -> 3 Surefire lanes, each 132 passed |
| Python S7f focused verification | `pytest tests/compose/schema/test_column_spec_metadata.py tests/compose/relation tests/compose/compilation/test_error_codes.py -q` -> 120 passed |
| Python S7f full regression | `pytest -q` -> 3468 passed |

## Changed Surface

| Area | Paths |
|---|---|
| Java relation model / capabilities | `foggy-dataset-model/src/main/java/com/foggyframework/dataset/db/model/engine/compose/relation`, `.../compilation` |
| Java outer query builder | `RelationOuterQueryBuilder.java`, `OuterQuerySpec.java`, `WindowSelectParser.java`, `WindowSelectSpec.java` |
| Java error codes and tests | `ComposeCompileErrorCodes.java`, relation / snapshot / compile tests |
| Java parity snapshots | `target/parity/_stable_relation_schema_snapshot.json`, `_stable_relation_outer_aggregate_snapshot.json`, `_stable_relation_outer_window_snapshot.json` |
| Python relation mirror | `src/foggy/dataset_model/engine/compose/relation`, `src/foggy/dataset_model/engine/compose/compilation/errors.py` |
| Python snapshot consumers | `tests/compose/relation`, `tests/compose/schema/test_column_spec_metadata.py`, `tests/compose/compilation/test_error_codes.py` |
| Python docs | `docs/v1.5/P2-post-v1.5-followup-execution-plan.md`, `docs/v1.5/S7b-stage7-runtime-contract-plan.md`, this quality record |

## Quality Checklist

| Check | Result | Notes |
|---|---|---|
| scope conformance | pass | Stage 7 stayed within stable relation runtime and mirror contract. It did not open relation join / union, materialized database views, named CTE, recursive CTE, or Python runtime outer aggregate / window. |
| code hygiene | pass | Java changed surface has no TODO / FIXME / debug print matches. Python scan only matched historical quality documents, not implementation files. |
| duplication and consolidation | pass-with-note | Snapshot consumer tests intentionally repeat contract assertions per snapshot family. This is acceptable while Java remains the source of truth. |
| complexity and abstraction | pass-with-follow-up | `RelationOuterQueryBuilder` is still acceptable for S7d-S7f, but it is now the main growth point. If S8 opens relation composition or in-memory post-processing, split parsing / validation / rendering strategies before adding more modes. |
| error handling and edge cases | pass | MySQL 5.7 CTE / window cases fail closed, SQL Server avoids `FROM (WITH`, ratio columns are rejected for aggregate / window where policy forbids it, and unsupported window frame clauses now fail closed. |
| readability and maintainability | pass | The `CompiledRelation`, `RelationSql`, `RelationCapabilities`, `OuterQuerySpec`, and parser objects keep runtime behavior explicit rather than hiding relation wrapping inside `QueryPlan`. |
| critical logic documentation | pass | S7b plan, S7f preflight, Java progress docs, and Python execution plan all document runtime boundaries, non-goals, and mirror-only status. |
| contract and compatibility | pass | `ColumnSpec` metadata remains excluded from equality / hash; S7a frozen snapshot stays consumable; S7e/S7f add capabilities through explicit reference policies and snapshots. |
| documentation and writeback | pass | Top-level status fields now reflect S7f completion and the Java quality follow-up commit. |
| test alignment | pass | Java focused tests cover runtime builder behavior and snapshots. Python tests verify model constants, capability parity, error constants, and Java snapshot consumption. |
| release readiness | ready-for-coverage-audit | No implementation blocker remains before coverage evidence audit. |

## Findings

- Fixed before audit: Java S7f `WindowSelectParser` previously extracted `ROWS` / `RANGE` frame clauses but did not validate their internal grammar. Commit `9a5ad62` now restricts frame clauses to approved bound forms and rejects unsupported frames with `relation-outer-window-not-supported`.
- Non-blocking note: S7e and S7f snapshots are regenerated from the current model state while retaining their stage contract versions. This is acceptable for the current Java-source-of-truth flow, but future snapshot policy should distinguish frozen historical evidence from regenerated current-model parity snapshots if long-term archival comparison is required.
- Non-blocking note: Python intentionally has no runtime outer aggregate / outer window implementation. That is a contract decision, not a missing mirror item.

## Risks / Follow-ups

- Run `foggy-test-coverage-audit` next to map S7a-S7f requirements to Java and Python evidence, especially dialect coverage for SQL Server, MySQL 5.7 fail-closed, ratio rejection, and frame rejection.
- Run `foggy-acceptance-signoff` after coverage audit if the S7 chain is ready to close.
- If the main line continues beyond S7, plan S8 separately around relation composition boundaries. Candidate topics are relation join / union policy, in-memory post-processing for small result sets, and runtime schema propagation after outer queries.
- Do not add more behavior into the same window expression string parser without either extending the restricted grammar explicitly or moving to a structured request object.

## Recommended Next Skills

- `foggy-test-coverage-audit`: required next step before formal signoff.
- `foggy-acceptance-signoff`: after coverage audit passes.

## Decision

- decision: `ready-for-coverage-audit`
- blocker: none
- follow_up_required: yes, coverage audit and formal signoff remain open
- quality_gate_result: S7 stable relation runtime chain can move from implementation quality gate to test evidence coverage audit.
