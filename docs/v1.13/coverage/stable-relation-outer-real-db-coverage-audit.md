---
doc_role: coverage-audit
doc_purpose: 盘点 v1.13 stable relation outer aggregate/window 三库真实执行测试证据覆盖情况
status: signed-off
---

# Stable Relation Outer Real DB Coverage Audit

## Document Purpose

- doc_type: coverage-audit
- intended_for: reviewer / test-owner / root-controller
- purpose: 确认 v1.13 对 stable relation S7e/S7f 三库 runtime oracle 的证据是否足够进入签收。

## Coverage Matrix

| Requirement | Criticality | Coverage | Evidence |
|---|---|---|---|
| Inline relation can be outer aggregated on SQLite/MySQL8/PostgreSQL | critical | covered | `test_outer_aggregate_groupby_oracle` |
| CTE relation can be hoisted and outer aggregated on SQLite/MySQL8/PostgreSQL | critical | covered | `test_outer_aggregate_cte_hoist_oracle` |
| CTE params are preserved in runtime execution | critical | covered | same test |
| Outer `RANK()` over derived ratio executes on SQLite/MySQL8/PostgreSQL | critical | covered | `test_outer_window_rank_oracle` |
| Outer moving average frame executes on SQLite/MySQL8/PostgreSQL | critical | covered | `test_outer_window_moving_avg_oracle` |
| Test compares against handwritten SQL oracle, not SQL text only | critical | covered | `test_stable_relation_outer_query_real_db_matrix.py` |
| Existing relation fail-closed unit coverage remains intact | critical | covered | `test_relation_outer_query_runtime.py` |

## Gaps

| Gap | Status | Reason |
|---|---|---|
| SQL Server live execution | not-covered | No SQL Server runtime fixture is part of this version. |
| Public DSL E2E | not-applicable | Stable relation outer query remains an internal compiler API. |
| Relation join / union source | not-applicable | Not part of S7e/S7f outer aggregate/window runtime. |

## Audit Conclusion

Coverage is sufficient for v1.13 acceptance. The prior v1.12 accepted risk around live MySQL8/PostgreSQL relation outer query execution is closed for the covered S7e/S7f behaviors.
