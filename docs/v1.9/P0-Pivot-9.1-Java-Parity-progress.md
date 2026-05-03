# P0 Pivot 9.1 Java Parity Progress

## 文档作用

- doc_type: progress
- intended_for: python-engine-agent / reviewer / signoff-owner
- purpose: 记录 Python v1.9 Pivot 9.1 parity 的执行进度、自检、测试证据和后续签收状态。

## 基本信息

- version: v1.9
- status: p5-stage5b-cascade-signed-off
- java_reference_commit: `10e863e9`
- python_baseline: `docs/v1.8/P0-Pivot-V9-Python-Parity-Gap-Report.md`
- owner: TBD
- completed_at: 2026-05-03

## 前置条件检查

| Item | Status | Notes |
|---|---|---|
| Java 9.1 version signoff reviewed | done | Read from `10e863e9` because current Java worktree is not signed-off file tree. |
| Python v1.8 S1-S3 baseline reviewed | done | Flat/grid oracle parity accepted in existing docs. |
| P0 planning docs created | done | `docs/v1.9` package. |
| P1 implementation approved | done | Cascade detector + rejection tests implemented and verified. |
| P2 managed relation feasibility approved | **done** | `docs/v1.9/P1-Pivot-9.1-Managed-Relation-Feasibility.md` — conditional-pass. |
| P3-A Stage 5A renderer design approved | **done** | `docs/v1.9/P2-Pivot-9.1-Stage5A-Renderer-Design.md` — design-only, no runtime. |

## Development Progress

| Phase | Task | Status | Notes |
|---|---|---|---|
| P0 | Requirement doc | done | Current package. |
| P0 | Implementation plan | done | Current package. |
| P0 | Code inventory | done | Current package. |
| P1 | Cascade detector | **done** | `src/foggy/dataset_model/semantic/pivot/cascade_detector.py` |
| P1 | Refusal error model | **done** | Stable error-code constants exported from `cascade_detector.py` |
| P1 | No-memory-fallback guard | **done** | `detect_cascade_and_raise()` called inside `executor.py` before translation |
| P1 | Cascade validation tests | **done** | `tests/test_dataset_model/test_pivot_v9_cascade_validation.py` — 21 tests |
| P2 | Managed relation feasibility | **done** | `docs/v1.9/P1-Pivot-9.1-Managed-Relation-Feasibility.md` — conditional-pass |
| P3-A | Stage 5A renderer design | **done** | `docs/v1.9/P2-Pivot-9.1-Stage5A-Renderer-Design.md` — design-only |
| P3-B | Stage 5A renderer prototype | **done** | `domain_transport.py` — SQLiteCteDomainRenderer + `build_join_predicate` + `assemble_domain_transport_sql` + 21 tests all executing assembled SQL |
| P3-C | Stage 5A SQLite production wiring + queryModel oracle parity | **done** | `domain_transport_plan` internal carrier + queryModel wiring + SQLite oracle parity |
| P3-D | Stage 5A MySQL8/PostgreSQL oracle parity + signoff | **done** | `tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py` — 3 DBs oracle parity verified. |
| P4 | C2 staged SQL cascade | **done** | P4 oracle parity and semantic boundaries verified. |
| P5 | Quality / coverage / acceptance | **done** | Quality gate, coverage audit, acceptance record completed. |

## Implementation Self-Check

Current P1 self-check:

- [x] Requirement scope is bounded.
- [x] Supported / refused / deferred / blocked cases are separated.
- [x] Public DSL change is explicitly out of scope.
- [x] Managed relation lifecycle is called out as a blocker.
- [x] Cascade detector added (`cascade_detector.py`).
- [x] `detect_cascade_and_raise()` wired into `executor.py` **before** the generic `hierarchyMode/expandDepth` axis-field checks and MemoryCubeProcessor path, ensuring `tree+cascade` returns `PIVOT_CASCADE_TREE_REJECTED` instead of the generic error.
- [x] All cascade rejection tests cover exact stable error-code prefixes (including `PIVOT_CASCADE_TREE_REJECTED`).
- [x] S3 regression suite passes (flat, grid, single TopN, having, crossjoin).
- [x] No memory fallback for cascade (detector raises before translation).
- [x] No public DSL was changed.
- [x] Stage 5A SQLite production wiring is isolated to internal `domain_transport_plan`; no public DSL change.
- [x] C2 cascade staged SQL generator added and verified.

## Testing Progress

## Current Testing Results

### Primary test commands

```powershell
pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py -q
```
**Result: included in 105-test Pivot regression pack**

```powershell
pytest -q
```
**Result: 3928 passed in 12.47s (0 failed)** — full repository regression clean on 2026-05-03.

### External DB tests (MySQL8 / Postgres)

External DB integration tests for Stage 5A domain transport are now fully implemented in `test_pivot_v9_domain_transport_real_db_matrix.py`.
- **MySQL8**: Tested against `localhost:13308` (`foggy_test` db). Verified `UNION ALL SELECT` CTE syntax with `<=>` NULL-safe matching. 0 skipped.
- **PostgreSQL**: Tested against `localhost:15432` (`foggy_test` db). Verified `VALUES` CTE syntax with `IS NOT DISTINCT FROM` NULL-safe matching. 0 skipped.
- **Oracle Parity**: 100% parity achieved across SQLite, MySQL8, and PostgreSQL for Additive SUM, Non-additive COUNT_DISTINCT, NULL member handling, systemSlice isolation, deniedColumns rejection, and OR-of-AND fallback generation.
- **Acceptance guard**: Real-DB transport tests force `threshold=0` for CTE cases and assert generated SQL contains `WITH _pivot_domain_transport` + `INNER JOIN _pivot_domain_transport`, preventing accidental fallback-only verification.

### Stage 5B C2 Cascade tests

```powershell
pytest tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```
**Result: 12 passed, 0 skipped**

```powershell
pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_domain_transport.py tests/test_dataset_model/test_pivot_v9_domain_transport_query_model.py tests/test_dataset_model/test_pivot_v9_cascade_semantics.py tests/integration/test_pivot_v9_domain_transport_real_db_matrix.py tests/integration/test_pivot_v9_cascade_real_db_matrix.py -q -rs
```
**Result: 105 passed, 0 skipped**

## P1 Fail-Closed Rules Implemented

| Rule | Error Code | Description |
|---|---|---|
| Two or more constrained fields on rows axis | `PIVOT_CASCADE_SQL_REQUIRED` | Requires staged SQL (Java 9.1 C2), blocked in Python P1. |
| limit without explicit orderBy | `PIVOT_CASCADE_ORDER_BY_REQUIRED` | Non-deterministic TopN is rejected. |
| hierarchyMode=tree + any constrained field | `PIVOT_CASCADE_TREE_REJECTED` | tree+cascade requires dedicated implementation. |
| columns axis with limit or having | `PIVOT_CASCADE_CROSS_AXIS_REJECTED` | Only rows-axis single-level is supported. |
| parentShare / baselineRatio + constrained field | `PIVOT_CASCADE_NON_ADDITIVE_REJECTED` | Derived metrics cannot participate in cascade. |

## Completed / Deferred

- **P3-B** Stage 5A renderer prototype — **complete (with executable closure)**. `SqliteCteDomainRenderer` generates CTE SQL + domain params only (no hardcoded alias). `build_join_predicate()` accepts `field_sql_map` from caller to produce correct left-side SQL expressions. `assemble_domain_transport_sql()` injects CTE prefix + INNER JOIN before WHERE/GROUP BY, producing directly executable SQL. 21 tests all execute assembled SQL on real SQLite.
- **P3-C** Stage 5A SQLite production wiring — **complete**. Pivot production path restored; internal `domain_transport_plan` uses `PrivateAttr`; large domain uses SQLite CTE transport; small domain uses OR-of-AND fallback; queryModel oracle parity covers SUM, COUNT_DISTINCT, NULL member, systemSlice, deniedColumns, schema isolation, and domain-only join.
- **P3-D** Stage 5A MySQL8/PostgreSQL oracle parity + signoff — **complete**. `Mysql8DomainRenderer` and `PostgresCteDomainRenderer` implementations are active. Three-DB (SQLite, MySQL8, Postgres) oracle parity validated on real `foggy_test` instances.
- **P4** C2 rows two-level cascade staged SQL — **complete**. `cascade_staged_sql.py` fully implemented and verified with NULL-safe CTE transport and cross-database oracle parity.
- **Staged SQL / DomainTransport** — SQLite, MySQL8, and PostgreSQL are wired and covered by real SQL oracle parity. No memory fallback is permitted for cascade.
- **Cascade subtotal/grandTotal** — deferred outside P4 CTE generation scope. Python's current `MemoryCubeProcessor` does not provide cascade subtotal rows equivalent to Java C2 totals; this remains a Python 9.2 follow-up unless separately prioritized.

## Experience Progress

- experience: N/A
- reason: Pure backend query engine planning; no UI interaction.

## Acceptance Criteria Mapping

| Requirement | Evidence | Status |
|---|---|---|
| P0 docs clearly define Java 9.1 parity boundary | `docs/v1.9/*` | done |
| P1 rejects unsupported cascade shapes | `tests/test_dataset_model/test_pivot_v9_cascade_validation.py` — 11 rejection tests | **done** |
| Cascade cannot enter current memory fallback | `detect_cascade_and_raise()` in `executor.py` fires before translation | **done** |
| Stage 5A/C2 blocked until managed relation proof | docs | done |
| SQLite/MySQL8/Postgres oracle required before runtime signoff | docs | done |
| S3 regression not broken | 36 targeted tests + 3859 full suite pass | **done** |
| P2 feasibility record produced | `docs/v1.9/P1-Pivot-9.1-Managed-Relation-Feasibility.md` | **done** |
| P2 clearly answers all 9 Core Questions | See feasibility doc | **done** |
| P3 conditionally unblocked | Feasibility conclusion: conditional-pass; design doc and oracle tests needed | **done** |
| P3-A design doc produced | `docs/v1.9/P2-Pivot-9.1-Stage5A-Renderer-Design.md` | **done** |
| P3-A covers all 11 required questions | API, SQL shape, params, NULL-safe, fail-closed, preAgg, oracle matrix | **done** |
| P3-B ready to start | Renderer prototype: SQLite first, then MySQL8/Postgres | **done** |
| P3-B renderer prototype implemented | `domain_transport.py` — SqliteCteDomainRenderer, `build_join_predicate`, `assemble` | **done** |
| P3-B assembled SQL executes (no `_base_` bug) | `TestAssembleDomainTransportSql` — 4 structural tests pass | **done** |
| P3-B SQLite oracle parity (SUM additive, assembled SQL) | `test_additive_sum_parity` | **done** |
| P3-B SQLite oracle parity (COUNT_DISTINCT non-additive, assembled SQL) | `test_non_additive_count_distinct_parity` — proves pre-agg | **done** |
| P3-B NULL-safe matching (assembled SQL) | `test_null_domain_member_parity` — SQLite IS operator | **done** |
| P3-B params ordering (assembled SQL with WHERE param) | `test_params_ordering_with_base_where_param` | **done** |
| P3-B SQLite param limit fail-closed | `test_params_limit_refuses` | **done** |
| P3-B unsupported dialect fail-closed | `test_none_dialect_refuses` + `test_mysql_refuses_in_p3b` | **done** |
| P3-B build_join_predicate (field_sql_map) | `TestBuildJoinPredicate` — 3 tests | **done** |
| P3-B full regression | Historical P3-B result: 3880 passed; superseded by final P5 full regression: 3928 passed | **done** |
| P3-C `domain_transport_plan` public schema isolation | `test_domain_transport_plan_schema_isolation` | **done** |
| P3-C domain-only join injection | `test_domain_join_without_explicit_selection` | **done** |
| P3-C small-domain OR-of-AND fallback | `test_size_fallback` | **done** |
| P3-C SQLite queryModel production parity | `test_pivot_v9_domain_transport_query_model.py` — 9 tests | **done** |
| P3-C Pivot regression pack | 66 targeted tests | **done** |

| P3-D MySQL8 and PostgreSQL renderer implementations | `domain_transport.py` — Mysql8DomainRenderer, PostgresCteDomainRenderer | **done** |
| P3-D Real DB oracle parity (MySQL8, Postgres) | `test_pivot_v9_domain_transport_real_db_matrix.py` | **done** |


| P4 Engine cleanup (no prints, deep copies) | cascade_staged_sql.py cleanup | **done** |
| P4 Real DB Oracle Parity (Cascade) | `test_pivot_v9_cascade_real_db_matrix.py` | **done** |
| P4 Semantic Boundary Coverage | `test_pivot_v9_cascade_semantics.py` | **done** |
| P5 Implementation quality gate | `docs/v1.9/quality/pivot-stage5b-c2-cascade-implementation-quality.md` | **done** |
| P5 Test coverage audit | `docs/v1.9/coverage/pivot-stage5b-c2-cascade-coverage-audit.md` | **done** |
| P5 Feature acceptance | `docs/v1.9/acceptance/pivot-stage5b-c2-cascade-acceptance.md` | **done** |

## Blockers

- No blocking items for the scoped P4 Stage 5B C2 cascade staged SQL signoff.
- preAgg + Pivot interaction: **decided in P3-A design** — preAgg does NOT participate in Pivot auxiliary queries.
- Cascade subtotal/grandTotal parity is explicitly deferred to Python 9.2 follow-up.

## 建议

Recommended next step:

1. Commit the scoped P4/P5 signoff files separately from unrelated dirty worktree changes.
2. Plan Python 9.2 follow-ups: cascade subtotal/grandTotal, SQL Server oracle, MySQL 5.7 live evidence, tree + cascade, telemetry.
