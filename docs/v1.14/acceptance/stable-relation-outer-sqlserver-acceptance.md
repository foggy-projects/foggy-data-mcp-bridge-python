---
acceptance_scope: feature
version: v1.14
target: stable-relation-outer-sqlserver-live-parity
doc_role: acceptance-record
doc_purpose: 记录 Python stable relation S7e/S7f outer aggregate/window SQL Server live oracle parity 的功能签收
status: signed-off
decision: accepted
signed_off_by: root-controller
signed_off_at: 2026-05-03
blocking_items: []
follow_up_required: yes
---

# Stable Relation Outer SQL Server Acceptance

## Document Purpose

- doc_type: acceptance
- intended_for: reviewer / root-controller / python-engine-agent
- purpose: 记录 v1.14 对 v1.13 仍未声明的 SQL Server stable relation outer runtime oracle 的补强结果。

## Requirement

v1.13 已签收 SQLite / MySQL8 / PostgreSQL 的 stable relation outer aggregate/window runtime oracle。v1.14 要求：

- 直接执行 `compile_outer_aggregate()` / `compile_outer_window()` 生成的 SQL Server SQL。
- 覆盖 inline relation 与 hoisted CTE relation。
- 验证 SQL Server `;WITH` hoist 形态真实执行，而不只是 snapshot marker。
- 与手写 SQL oracle 比对结果。
- 不改变 public DSL 或 query lifecycle。

## Implemented Evidence

| Behavior | Status | Evidence |
|---|---|---|
| SQL Server outer aggregate groupBy | covered | `test_outer_aggregate_groupby_oracle[sqlserver]` |
| SQL Server outer aggregate with `;WITH` CTE hoist | covered | `test_outer_aggregate_cte_hoist_oracle[sqlserver]` |
| SQL Server outer rank over derived ratio | covered | `test_outer_window_rank_oracle[sqlserver]` |
| SQL Server outer moving average frame | covered | `test_outer_window_moving_avg_oracle[sqlserver]` |
| Four-dialect oracle matrix | covered | `test_stable_relation_outer_query_real_db_matrix.py` |

## Verification

```powershell
pytest tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 16 passed in 1.61s

pytest tests/compose/relation/test_relation_outer_query_runtime.py tests/integration/test_stable_relation_outer_query_real_db_matrix.py -q -rs
# 25 passed in 1.30s

pytest -q
# 3977 passed in 13.57s
```

## Decision

Feature-level acceptance is `accepted`.

Stable relation S7e/S7f outer aggregate/window now has live runtime oracle evidence across SQLite, MySQL8, PostgreSQL, and SQL Server. This closes the stable relation runtime evidence gap called out in v1.11-v1.13.
