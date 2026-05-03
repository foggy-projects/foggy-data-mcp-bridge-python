---
acceptance_scope: feature
version: v1.13
target: stable-relation-outer-real-db-parity
doc_role: acceptance-record
doc_purpose: 记录 Python stable relation S7e/S7f outer aggregate/window 三库真实执行 oracle parity 的功能签收
status: signed-off
decision: accepted
signed_off_by: root-controller
signed_off_at: 2026-05-03
blocking_items: []
follow_up_required: yes
---

# Stable Relation Outer Real DB Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: reviewer / root-controller / python-engine-agent
- purpose: 记录 v1.13 对 v1.12 accepted-with-risks 中 MySQL8/PostgreSQL 真实执行缺口的补强结果。

## Requirement

v1.12 已实现内部 stable relation outer aggregate/window runtime，但只声明 SQLite oracle 与 dialect marker/refusal 证据。v1.13 要求：

- 直接执行 `compile_outer_aggregate()` / `compile_outer_window()` 生成的 SQL。
- 在 SQLite / MySQL8 / PostgreSQL 三库运行。
- 与手写 SQL oracle 逐结果集比对。
- 不改变 public DSL 或 query lifecycle。

## Implemented Evidence

| Behavior | Status | Evidence |
|---|---|---|
| outer aggregate groupBy | covered | `test_outer_aggregate_groupby_oracle` |
| outer aggregate with CTE hoist | covered | `test_outer_aggregate_cte_hoist_oracle` |
| CTE params order | covered | same as above |
| outer rank over derived ratio | covered | `test_outer_window_rank_oracle` |
| outer moving average over measure | covered | `test_outer_window_moving_avg_oracle` |
| SQLite runtime oracle | covered | fixture matrix |
| MySQL8 runtime oracle | covered | fixture matrix, 0 skipped |
| PostgreSQL runtime oracle | covered | fixture matrix, 0 skipped |

## Verification

```powershell
pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 12 passed in 0.94s

pytest tests/compose/relation/test_relation_outer_query_runtime.py tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 21 passed in 0.87s

pytest -q
# 3973 passed in 14.17s
```

## Decision

Feature-level acceptance is `accepted`.

The v1.12 live MySQL8/PostgreSQL evidence gap is closed for stable relation outer aggregate/window. SQL Server live execution remains out of scope and should stay as a later explicit oracle task if required.
