# P1 timeWindow Python parity progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: 跟踪 Python 引擎对 Java SemanticDSL `timeWindow` 能力的分阶段对齐进度

## 基本信息

- version: v1.5 follow-up
- priority: P1
- status: signed-off
- delivery_mode: single-root-delivery
- source_type: cross-project parity follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- upstream_java_acceptance: `foggy-data-mcp-bridge/docs/8.3.0.beta/acceptance/P1-SemanticDSL-TimeWindow-Java-acceptance.md`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-28
- acceptance_record: docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md
- blocking_items: none
- follow_up_required: yes

## 背景

Java 侧 `timeWindow` 已完成 DSL 解析、QueryPlan 编译、MySQL/MySQL8 方言实跑校验和正式签收。Python 侧 v1.5 已签收的是计算字段编译器架构对齐，不包含顶层 `timeWindow` 查询意图。

本跟踪项用于把 Python parity 拆成可独立验收的阶段，先保证 MCP/SPI 契约不丢字段，再进入查询计划和 SQL 展开。

## 目标

- Python `SemanticQueryRequest` 接收并按 Java camelCase 输出 `timeWindow`。
- MCP `build_query_request` 从 Java 格式 payload 构造请求时保留 `timeWindow` 原始结构。
- 后续补齐 Python QueryPlan / SQL execution 对 Java `timeWindow` 的语义展开。
- 已先补齐 rolling / cumulative 的窗口投影 IR，作为后续 QueryPlan lowering 的输入。
- 已接入 rolling / cumulative 的两层 SQL preview / execution path：内层按时间粒度聚合，外层做窗口投影。
- 已接入 rolling / cumulative 路径上的 `value` / `range` lowering：`[)` / `[]` 会进入 base CTE 的时间字段过滤，并通过 bind params 传参。
- 已接入 comparative period 的 base CTE self-join path：yoy / mom / wow 输出 `__prior` / `__diff` / `__ratio` 派生列。
- 已补真实 DB 执行矩阵：SQLite 自动化实跑覆盖 rolling range + yoy；本地 MySQL8 / Postgres demo 库手动探针覆盖 rolling range + yoy 自连接。
- 已通过 MySQL8 2025 sales fact seed 复核 yoy 非空 prior/diff/ratio，避免只验证 SQL 可执行但 prior 全为空。

## 非目标

- 当前阶段不实现 `timeWindow` 到 SQL 的完整编译。
- 当前阶段不引入跨方言时间粒度函数翻译。
- 当前阶段不扩大 v1.5 计算字段编译器的已签收范围。

## 开发进度

- [x] S0. DTO / SPI payload parity
  - `SemanticQueryRequest.time_window` 新增 Java alias `timeWindow`
  - `build_query_request` 透传 `payload["timeWindow"]`
  - Java alignment 测试覆盖 camelCase 反序列化、序列化和 Accessor payload passthrough
- [x] S1. Validator parity + fail-closed service guard
  - 新增 Python `TimeWindowDef` / `TimeWindowValidator`，错误码和兼容矩阵对齐 Java 8.3.0.beta
  - `RelativeDateParser.is_valid` 覆盖 `now`、相对日期、ISO 日期和 compact 日期
  - `SemanticQueryService` 对合法 `timeWindow` 明确返回 `TIMEWINDOW_NOT_IMPLEMENTED`，避免静默忽略后给出错误结果
  - 非法 `timeWindow` 先返回 Java 对齐的 `TIMEWINDOW_*` 错误码
- [x] S2. Window expansion IR parity
  - 新增 `TimeWindowExpander`，先将 rolling / cumulative 展开为窗口投影 IR
  - rolling 输出 `ROWS BETWEEN n-1 PRECEDING AND CURRENT ROW`，partition 使用非时间 `groupBy`
  - ytd / mtd 输出 `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`，partition 自动补 `$year` / `$month`
  - `TimeWindowProjectedColumn.to_calculated_field()` 生成后续 SQL lowering 可复用的 calculated field 字典
  - 该阶段只补中间表示和单测，不改变 `SemanticQueryService` 的 fail-closed 行为
- [x] S3a. Rolling / cumulative two-stage SQL path
  - `_build_query` 对 `timeWindow` 分流到专用两层 SQL 生成器
  - 内层 CTE 使用 QM 字段名作为稳定 SQL alias，避免 Java expected columns 丢失
  - rolling / ytd / mtd 外层 `OVER` 使用 S2 IR 的 frame / partition / orderBy
  - 与 `calculatedFields` 组合仍 fail-closed
- [x] S3b.1 Value / range lowering parity
  - 将 `value` / `range` 转为时间字段过滤，覆盖 absolute / relative / now
  - `[)` 生成 `>= start AND < end`，`[]` 生成 `>= start AND <= end`
  - 过滤注入 base CTE，确保窗口函数基于已裁剪时间范围计算
  - 参数继续走现有 bind params，不内联用户输入
- [x] S3b.2 Real DB / dialect parity matrix
  - SQLite 自动化实库测试覆盖 rolling range 参数绑定、窗口聚合结果和 yoy prior/diff/ratio 结果
  - MySQL8 / Postgres 本地 demo 库通过 `SemanticQueryService + Executor` 真实执行 rolling range 和 yoy 自连接
  - 修复 executor 未显式传 dialect 时 MySQL timeWindow CTE alias 使用 ANSI 双引号的问题，改为从 `MySQLExecutor / PostgreSQLExecutor / SQLiteExecutor` 自动推断方言
  - 修复 Postgres strict bind 下 compact date key 被解析成字符串导致 integer 参数不匹配的问题，date-like `$id` + `*_key` 自动绑定为整数
  - MySQL8 demo 侧补充确定性 2025 `fact_sales` seed 脚本：`foggy-data-mcp-bridge/foggy-dataset-demo/docker/mysql/init/04-seed-2025-sales.sql`（commit `9f63739`）
- [x] S3c. Comparative period SQL path
  - yoy / mom / wow 使用 base CTE self-join 展开，不复用 rolling/cumulative 窗口 IR
  - compare period 输出 `metric__prior` / `metric__diff` / `metric__ratio`
  - `validate_query_fields` 已识别 comparative 派生列，避免预校验误拒
  - 质量复核修复 wow/week join 条件与模型 week 字段缺口，防止周粒度比较退化或字段不可用（commit `479ca3a`）
- [x] S4. 覆盖审计与验收
  - 已完成 implementation quality gate：`docs/v1.5/quality/P1-timeWindow-Python-parity-implementation-quality.md`
  - 已完成 coverage audit：`docs/v1.5/coverage/P1-timeWindow-Python-parity-coverage-audit.md`
  - 已完成 feature acceptance signoff：`docs/v1.5/acceptance/P1-timeWindow-Python-parity-acceptance.md`
  - 结论：`accepted-with-risks`，无阻断项；遗留为 MySQL8/Postgres CI 自动化、Java/Python golden diff、`timeWindow + calculatedFields` 后续增强

## 测试进度

- [x] `python -m pytest tests/test_mcp/test_java_alignment.py -q`
  - result: 25 passed
  - coverage: `SemanticQueryRequest` alias parity, response/request Java shape, `build_query_request` passthrough
- [x] `python -m pytest tests/test_dataset_model/test_time_window.py -q`
  - result: 35 passed
  - coverage: Java validator mirror, relative date validation/resolution, rolling/cumulative expansion IR, rolling/ytd/mtd two-stage SQL preview, `[)` / `[]` range lowering, yoy/mom/wow comparative self-join SQL preview, MySQL executor dialect inference
- [x] `python -m pytest tests/test_dataset_model/test_time_window_sqlite_execution.py -q`
  - result: 2 passed
  - coverage: SQLite real execution for rolling range and yoy comparative period
- [x] `python -m pytest tests/test_dataset_model/test_time_window.py tests/test_dataset_model/test_time_window_sqlite_execution.py tests/test_dataset_model/test_window_functions.py tests/test_mcp/test_java_alignment.py -q`
  - result: 86 passed
  - coverage: timeWindow S3b.2/S3c + SQLite real execution + existing calculatedFields window functions + MCP Java alignment
- [x] `python -m pytest tests/test_dataset_model/test_sql_quoting_and_errors.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q`
  - result: 37 passed
  - coverage: dialect quoting/function paths after executor dialect inference change
- [x] Real DB / dialect parity probes
  - SQLite: automated pytest, rolling range returns expected daily window sums; yoy Jan 2024 returns current/prior/diff/ratio
  - MySQL8: local `foggy-demo-mysql8` (`localhost:13308`, MySQL 8.0.44), rolling range returned 7 rows with numeric rolling values; yoy self-join executed successfully
  - MySQL8 2025 seed verification: `fact_sales` has 3179 `TW2025%` rows, `date_key` range `20250101..20250331`; Python `SemanticQueryService` yoy query returned 3 rows for 2025 with non-null `salesAmount__prior`, `salesAmount__diff`, and `salesAmount__ratio`
  - Postgres: local `foggy-demo-postgres` (`localhost:15432`, PostgreSQL 15.17), rolling range returned 7 rows with numeric rolling values; yoy self-join executed successfully

## Experience Progress

- status: N/A
- reason: 纯后端 / API 契约变更，无 UI 页面或交互流程。

## Execution Check-in

### Completed

- Python SPI 请求模型已保留 `timeWindow` 顶层字段。
- MCP accessor 构造请求时不会丢弃 Java payload 中的 `timeWindow`。
- 已用 Java alignment 单测锁住外部 JSON 使用 `timeWindow`，不输出 `time_window`。
- Python 已镜像 Java validator 基础契约，覆盖 grain / comparison / range / value / targetMetrics / rollingAggregator 校验。
- Service 层已 fail-closed，合法 `timeWindow` 不再被静默忽略。
- Python 已补 rolling / cumulative window expansion IR，对齐 Java 窗口 frame、partition、orderBy、alias 和默认聚合策略。
- Python 已补 rolling / ytd / mtd 两层 SQL 生成路径，避免单层聚合窗口混用。
- Python 已补 rolling / cumulative 路径上的 `value` / `range` lowering，支持 `[)` / `[]` 和 absolute / relative / now 值解析。
- Python 已补 yoy / mom / wow comparative self-join SQL path，输出 prior / diff / ratio 派生列。
- Python 质量复核已修复 wow/week 语义对齐问题，并补齐 demo model 的 `salesDate$week` 字段暴露。
- `validate_query_fields` 已识别 timeWindow 动态列，Java 风格 columns 不再被预校验误拒。
- Python 已补 timeWindow SQLite 自动化实库测试，并完成 MySQL8 / Postgres 本地 demo 库真实执行探针。
- `SemanticQueryService` 已支持从 executor 自动推断 SQL dialect，MySQL 执行链路不再因为双引号 alias 生成错误结果或语法错误。
- compact date key 的 timeWindow range bind params 已按 date-like `$id` / `*_key` 转为整数，避免 Postgres asyncpg 严格参数类型报错。
- Java/demo 仓库已新增 MySQL8 2025 `fact_sales` 确定性 seed 脚本，Python 实库 yoy 已验证 2025 prior 不再为空。

### Touched Code Areas

- `src/foggy/mcp_spi/semantic.py`
- `src/foggy/mcp_spi/accessor.py`
- `src/foggy/dataset_model/semantic/time_window.py`
- `src/foggy/dataset_model/semantic/field_validator.py`
- `src/foggy/dataset_model/semantic/service.py`
- `src/foggy/demo/models/ecommerce_models.py`
- `tests/test_mcp/test_java_alignment.py`
- `tests/test_dataset_model/test_time_window.py`
- `tests/test_dataset_model/test_time_window_sqlite_execution.py`
- `docs/v1.5/P1-timeWindow-Python-parity-progress.md`

### Self-check

- [x] scope limited to DTO / MCP payload passthrough
- [x] nested `timeWindow` keys kept unchanged for Java payload compatibility
- [x] snake_case internal attr still usable through Pydantic `populate_by_name`
- [x] validator error codes mirror Java names
- [x] service no longer silently ignores executable `timeWindow`
- [x] rolling / cumulative expander IR mirrors Java frame and partition rules
- [x] S2 does not enable SQL execution before QueryPlan lowering is ready
- [x] S3a uses a CTE base aggregate before outer window projection
- [x] S3b.1 lowers `value` / `range` into base CTE time filters with bind params
- [x] S3b.2 real DB execution covered for SQLite automated path and MySQL8/Postgres local demo probes
- [x] S3c lowers comparative period into base CTE self-join SQL
- [x] quality review fix for wow/week parity verified by focused tests
- [x] MySQL8 2025 seed verified with non-null yoy prior/diff/ratio through Python service
- [x] calculatedFields combination still fails closed
- [x] focused tests passed
- [x] remaining coverage audit / acceptance work recorded explicitly

### Acceptance Readiness

- current_stage: S4 signed-off
- overall_item: signed-off
- decision: accepted-with-risks
- reason: implementation, quality fix, coverage audit, and feature acceptance signoff are complete; remaining items are non-blocking long-term regression / feature-extension follow-ups.

## 遗留项

- MySQL8 / Postgres 实库探针目前不是 CI 自动化矩阵，后续可补 docker-backed integration profile。
- G1 follow-up 已启动并补齐 pytest 集成矩阵：`docs/v1.5/P1-timeWindow-real-db-integration-matrix-progress.md` / `tests/integration/test_time_window_real_db_matrix.py`。当前本地 MySQL8 + Postgres demo 库实跑 13 passed；CI docker-backed profile 仍可后续独立接入。
- Java ↔ Python `timeWindow` golden output 自动化未建设，后续两端继续演进时可补。
- G2 follow-up 已启动：`docs/v1.5/P1-timeWindow-java-python-golden-diff-progress.md` / `tests/test_dataset_model/test_time_window_java_parity_catalog.py`。Java fixture 来源为 `foggy-data-mcp-bridge-wt-dev-compose` 的 8.3.0.beta 已签收 timeWindow parity catalog。
- G3/P3 follow-up 已启动设计记录：`docs/v1.5/P1-timeWindow-calculatedFields-design-progress.md`。当前结论是 Java `dev-compose` G6 仍 open，Python 保持 fail-closed；首个可落地子集建议限定为 timeWindow 结果列之上的后置 scalar calculatedFields。
