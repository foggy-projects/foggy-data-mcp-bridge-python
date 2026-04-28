# P1 timeWindow real DB integration matrix progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: 跟踪 Python timeWindow 签收后遗留项 G1 的 MySQL8 / Postgres 真实数据库自动化矩阵补齐

## 基本信息

- version: v1.5 follow-up
- priority: P1
- status: ready-for-review
- source_type: post-acceptance follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- upstream_acceptance: `docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`
- related_gap: G1 - MySQL8 / Postgres real DB probes not in pytest matrix

## 目标

- 将 S4 签收时的 MySQL8 / Postgres 手动探针固化为可重复执行的 pytest integration matrix。
- 覆盖 rolling range、ytd/mtd cumulative、yoy/mom/wow comparative period，以及 MySQL8 2025 yoy seed 非空 prior/diff/ratio。
- 数据库不可用时跳过对应用例；数据库可用时必须执行真实 SQL 并校验结果。

## 开发进度

- [x] 新增 `tests/integration/test_time_window_real_db_matrix.py`
  - MySQL8 demo: `localhost:13308 / foggy_test`
  - Postgres demo: `localhost:15432 / foggy_test`
  - 使用真实 `SemanticQueryService + Executor` 执行，不停留在 SQL preview。
- [x] 修复 demo model 的 week 字段物理映射
  - 语义字段保持 `salesDate$week`
  - 物理列对齐 demo schema：`dim_date.week_of_year`
  - 避免 wow/week 在真实 MySQL8/Postgres 上生成 `dd.week`。
- [x] 同步 SQLite timeWindow fixture schema
  - SQLite fixture 改为 `week_of_year`，保持与 Java/demo 数据库 schema 一致。
- [x] 累计窗口排序参数收敛
  - ytd/mtd 集成测试统一按 `group_by` 排序，避免向 `SemanticQueryRequest` 传入 `None`。

## 测试进度

- [x] `python -m pytest tests/integration/test_time_window_real_db_matrix.py -q`
  - result: 13 passed
  - coverage: MySQL8 + Postgres rolling range / ytd / mtd / yoy / mom / wow / MySQL8 2025 yoy seed
- [x] `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_mcp/test_java_alignment.py -q`
  - result: 63 passed
  - coverage: SQL preview, SQLite execution, MCP Java alignment

## Execution Check-in

### Completed

- P1 matrix 已从手动探针推进为自动化 pytest 集成测试。
- 集成测试发现并修复了 `salesDate$week` 语义字段到物理列 `week_of_year` 的真实 schema 映射问题。
- MySQL8 / Postgres 两个引擎当前在 CTE、rolling/cumulative/comparative timeWindow，以及后置 scalar calculatedFields 的真实执行路径均通过矩阵校验。

### Self-check

- [x] 不要求本地数据库一定存在；不可用时按库维度 skip。
- [x] 一旦数据库可连接，必须校验真实执行结果和非空派生指标。
- [x] 未改变外部语义字段名，仍对外暴露 `salesDate$week`。
- [x] 原有 SQLite 和 Java alignment 回归通过。

## 后续

- P2: 建设 Java ↔ Python `timeWindow` golden output diff，覆盖 SQL shape / params / columns。
- P3: 已按 Java 8.5.0 契约补齐后置 scalar `timeWindow + calculatedFields` 子集，并纳入本实库矩阵。
