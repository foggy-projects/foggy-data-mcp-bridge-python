# P1 timeWindow Python parity progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer
- purpose: 跟踪 Python 引擎对 Java SemanticDSL `timeWindow` 能力的分阶段对齐进度

## 基本信息

- version: v1.5 follow-up
- priority: P1
- status: in-progress
- delivery_mode: single-root-delivery
- source_type: cross-project parity follow-up
- owning_repo: `foggy-data-mcp-bridge-python`
- upstream_java_acceptance: `foggy-data-mcp-bridge/docs/8.3.0.beta/acceptance/P1-SemanticDSL-TimeWindow-Java-acceptance.md`

## 背景

Java 侧 `timeWindow` 已完成 DSL 解析、QueryPlan 编译、MySQL/MySQL8 方言实跑校验和正式签收。Python 侧 v1.5 已签收的是计算字段编译器架构对齐，不包含顶层 `timeWindow` 查询意图。

本跟踪项用于把 Python parity 拆成可独立验收的阶段，先保证 MCP/SPI 契约不丢字段，再进入查询计划和 SQL 展开。

## 目标

- Python `SemanticQueryRequest` 接收并按 Java camelCase 输出 `timeWindow`。
- MCP `build_query_request` 从 Java 格式 payload 构造请求时保留 `timeWindow` 原始结构。
- 后续补齐 Python QueryPlan / SQL execution 对 Java `timeWindow` 的语义展开。
- 已先补齐 rolling / cumulative 的窗口投影 IR，作为后续 QueryPlan lowering 的输入。

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
- [ ] S3. QueryPlan / SQL execution parity
  - 将 S2 IR 接入查询计划，避免直接塞入单层 SELECT 后产生错误聚合语义
  - MySQL / Postgres / SQLite 方言的时间 bucket 和 range 展开
  - rolling / cumulative 实跑输出结构与 Java 对齐
- [ ] S3b. Comparative period parity
  - yoy / mom / wow 需要 derived plan / self-join 类展开，暂不借 rolling/cumulative IR 误开执行
  - compare period 输出结构与 Java 对齐
- [ ] S4. 覆盖审计与验收
  - 回补 QueryPlan 单测、SQL 快照测试和必要的集成测试
  - 进入 coverage audit / acceptance signoff

## 测试进度

- [x] `python -m pytest tests/test_mcp/test_java_alignment.py -q`
  - result: 25 passed
  - coverage: `SemanticQueryRequest` alias parity, response/request Java shape, `build_query_request` passthrough
- [x] `python -m pytest tests/test_dataset_model/test_time_window.py -q`
  - result: 25 passed
  - coverage: Java validator mirror, relative date validation, rolling/cumulative expansion IR, model field collection, service fail-closed guard
- [ ] QueryPlan / SQL parity tests
  - status: not-started
  - reason: QueryPlan / SQL execution 尚未实现

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

### Touched Code Areas

- `src/foggy/mcp_spi/semantic.py`
- `src/foggy/mcp_spi/accessor.py`
- `src/foggy/dataset_model/semantic/time_window.py`
- `src/foggy/dataset_model/semantic/service.py`
- `tests/test_mcp/test_java_alignment.py`
- `tests/test_dataset_model/test_time_window.py`
- `docs/v1.5/P1-timeWindow-Python-parity-progress.md`

### Self-check

- [x] scope limited to DTO / MCP payload passthrough
- [x] nested `timeWindow` keys kept unchanged for Java payload compatibility
- [x] snake_case internal attr still usable through Pydantic `populate_by_name`
- [x] validator error codes mirror Java names
- [x] service no longer silently ignores executable `timeWindow`
- [x] rolling / cumulative expander IR mirrors Java frame and partition rules
- [x] S2 does not enable SQL execution before QueryPlan lowering is ready
- [x] focused tests passed
- [x] remaining QueryPlan / SQL work recorded explicitly

### Acceptance Readiness

- current_stage: S2 ready-for-review
- overall_item: not-ready-for-acceptance
- reason: full Java parity still requires QueryPlan and SQL execution implementation.

## 遗留项

- Python 引擎尚未把 `timeWindow` 编译为时间 bucket / range / compare 查询计划。
- Python S2 仅提供 rolling / cumulative 的窗口投影 IR，服务层仍 fail-closed。
- Python yoy / mom / wow comparative period 仍需单独 QueryPlan 展开，不能复用 rolling/cumulative 单层窗口逻辑。
- Python 尚未补 MySQL8 等价实跑矩阵。
- Java 已签收，Python parity 后续应单独验收，不能借 Java 结论直接关闭。
