# P0 Pivot V9 Python Parity Gap Report

## 文档作用

- doc_type: audit + execution-plan
- status: s3-grid-shaping-and-axis-operations-complete
- date: 2026-05-02
- owning_repo: `foggy-data-mcp-bridge-python`
- java_reference_repo: `foggy-data-mcp-bridge-wt-dev-compose`
- java_reference_version: `docs/9.0.0.beta`
- purpose: 盘点 Python 引擎与 Java Pivot V9 release-ready 能力之间的差距，并给出 Python 侧可执行分期。

## 审计结论

Python 引擎已完成 Pivot V9 对齐的 S1 合同层、S2/S2.1 Flat Pivot MVP、S3 Grid Shaping + Axis Operations：`outputFormat=flat/grid`、native metrics、`rows + columns` 降维、`slice/systemSlice/deniedColumns`、grid `rowHeaders/columnHeaders/cells`、axis `having/orderBy/limit`、`crossjoin` 已能执行并通过 SQLite/MySQL8/Postgres 真实 SQL oracle parity。现有可执行能力仍主要覆盖 8.x/早期 V3 查询路径与 Pivot S3 子集：

- `columns`
- `groupBy`
- `slice`
- `orderBy`
- `calculatedFields`
- `timeWindow`
- `fieldAccess` / `systemSlice` / `deniedColumns`
- 旧的 `withSubtotals` 字段声明

S3 后 Python 侧已经公开并解析 `pivot` AST，也能把 Flat/Grid Pivot 安全翻译到既有语义查询路径执行并完成内存 shaping；但仍没有 subtotal/tree/properties/non-additive rollup，也没有 S11/S12 的结构化衍生指标运行时：

- `parentShare` 执行
- `baselineRatio` 执行
- `pivot.properties` 后置贴合
- `tree` result shaping
- `subtotal/tree/non-additive rollup` 内存算法

因此当前不能宣称 Python 引擎已经覆盖 Java Pivot V9 或与 MDX 替代场景对齐。Python 侧应进入独立 P0 parity 项目，而不是在现有 `groupBy` 路径上零散补字段。

## S1 完成状态

S1 已完成，范围限定为合同层与 fail-closed shell：

- `SemanticQueryRequest` 新增 `pivot: Optional[PivotRequest]`。
- 新增 Pydantic DTO：`PivotRequest`、`PivotAxisField`、`PivotMetricItem`、`PivotOptions`、`PivotLayout`。
- `build_query_request()` 已透传并解析 `payload.pivot`。
- MCP schema 已公开 `pivot.rows/columns/metrics/properties/options/layout/outputFormat`。
- Schema 与 DTO 均禁止 metric `expr`，不开放 `CELL_AT` / `AXIS_MEMBER` / `ROLLUP_TO`。
- Schema 前置声明 `pivot + columns`、`pivot + timeWindow` 互斥。
- `SemanticQueryService.query_model()`、`build_query_with_governance()`、`_build_query()` 均对 pivot 请求返回或抛出 `PIVOT_NOT_IMPLEMENTED_IN_PYTHON`，避免静默走旧 SQL 路径。

验证：

- `python -m json.tool src/foggy/mcp/schemas/query_model_v3_schema.json`
- `pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py -q`，6 passed

## 当前证据

### 已存在的基础能力

| 能力 | Python 现状 | 证据 |
|---|---|---|
| Java camelCase request DTO | 已存在 | `src/foggy/mcp_spi/semantic.py` 的 `SemanticQueryRequest` |
| payload 到 DTO 解析 | 已存在 | `src/foggy/mcp_spi/accessor.py` 的 `build_query_request()` |
| `calculatedFields` | 已存在 | `SemanticQueryRequest.calculated_fields` + `SemanticQueryService._build_query()` |
| `timeWindow` | 已存在，且已有 SQLite / MySQL8 / Postgres / SQL Server 方向的测试基础 | `src/foggy/dataset_model/semantic/time_window.py`、`tests/integration/test_time_window_real_db_matrix.py` |
| 权限参数 | 已存在 | `fieldAccess`、`systemSlice`、`deniedColumns` 已进入 DTO / accessor / governance |
| TM measure 默认聚合 | 已存在 | `DbModelMeasureImpl.aggregation` 默认 `SUM`，支持 `COUNT_DISTINCT` 等 |

### 明确缺失

| Java Pivot V9 能力 | Python 状态 | 影响 |
|---|---|---|
| `payload.pivot` schema | S1 已补 | MCP 层已有 Pivot DSL 合同；非 S2 flat 子集仍 fail-closed |
| Pivot AST / Pydantic model | S1 已补 | 可表达 rows/columns/metrics/options/layout |
| `pivot.metrics` mixed array | S1 已补 | 可解析 native / parentShare / baselineRatio；暂不执行 |
| Flat Pivot runtime | S2/S2.1 已补 | `outputFormat=flat` 可翻译为既有 `groupBy + columns` 查询路径并执行 |
| Full Pivot runtime pipeline | 部分已补 | S2/S3 已覆盖 flat/grid、having、TopN、crossjoin；S4/S5 仍缺 subtotal/tree/non-additive/derived metric |
| `flat/grid/tree` result shaping | 部分已补 | flat/grid 已补；tree 仍缺 |
| Axis `having` | S3 已补 | 支持聚合后成员过滤，并有 SQLite/MySQL8/Postgres oracle parity |
| Axis `limit/orderBy` per-group TopN | S3 已补 | 支持 S3 范围内的单层/受控 TopN，并有 oracle parity |
| `crossjoin` 稀疏补全 | S3 已补 | grid 采用 Option A full matrix 语义，缺失 cell 输出 None |
| `rowSubtotals/columnSubtotals/grandTotal` | 缺失 | 旧 `withSubtotals` 仅是声明，不等价于 V9 Pivot subtotal |
| `properties` 后置属性贴合 | 缺失 | 非分组属性无法安全贴合 |
| `hierarchyMode=tree` | 缺失 | 父子层级 Pivot 无法执行 |
| non-additive rollup cache | 缺失 | `COUNT_DISTINCT` / ratio subtotal 无法保证正确 |
| `parentShare` | 缺失 | 子项占父级比例缺口 |
| `baselineRatio` | 缺失 | 首末/基准比较缺口 |
| SQL parity harness for Flat Pivot | S2/S2.1 已补 | 已与 SQLite/MySQL8/Postgres 真实 SQL oracle 对比 |
| SQL parity harness for Grid Pivot | S3 已补 | 已与 SQLite/MySQL8/Postgres 真实 SQL oracle 对比 |
| SQL parity harness for Subtotal/Derived Pivot | 缺失 | 后续阶段尚无法证明 S4/S5 语义 parity |
| Java response snapshot parity | 缺失 | 无法证明 Python shape 与 Java shape 一致 |

## 与 Java V9 设计的对齐判断

### 可复用的 Python 基础设施

Python 侧不需要从零开始：

1. `SemanticQueryService._build_query()` 已能把字段解析、JOIN、measure 聚合、calculatedFields、slice、orderBy 编译成 SQL。
2. `build_query_with_governance()` 已暴露治理后 SQL 编译入口，后续 Pivot Phase 1 可以复用。
3. `DbQueryResult` / executor 层已能承接 SQLite、MySQL、Postgres 等数据库。
4. 现有 integration parity 目录已经有 Java snapshot / real DB matrix 的组织方式，可复用为 Pivot parity harness。
5. 权限链路已经有 `systemSlice` merge 和 `deniedColumns` 转 QM field 的基础，后续必须在 Pivot Phase 1 前复用。

### 不能复用或不能直接等价的部分

1. 旧 `withSubtotals` 不是 V9 Pivot subtotal。
   - Python 代码只保留 DTO/schema/prompt 层声明，没有发现运行时 `_rowType` subtotal 注入逻辑。
   - V9 的 subtotal 需要按 row/column/grand total、non-additive cache 和 `_sys_meta` 坐标打标执行。
2. 普通 `groupBy + columns` 不能替代 `pivot.rows/columns/metrics`。
   - Pivot 需要先降维成基础聚合，再执行内存域操作和 shaping。
   - `columns` 与 `pivot` 在 Java 侧是互斥契约。
3. `calculatedFields` 不能直接承接 S11/S12 衍生指标。
   - Java 已将 `parentShare` / `baselineRatio` 收敛为 `pivot.metrics` 里的结构化 metric item。
   - Python 若继续让 LLM 写表达式，会重新引入 `ROLLUP_TO` / `CELL_AT` 心智负担。

## 建议分期

### S1 - Contract Snapshot & Fail-Closed Shell

状态：已完成。

目标：先让 Python 接住 Java Pivot V9 DSL，并在未实现运行时前 fail-closed。

范围：

- 增加 Pydantic AST：
  - `PivotRequest`
  - `PivotAxisField`
  - `PivotMetricItem`
  - `PivotOptions`
  - `PivotLayout`
- `SemanticQueryRequest` 增加 `pivot: Optional[PivotRequest]`。
- `build_query_request()` 解析 `payload.pivot`。
- MCP schema 同步 Java V9：
  - `pivot + columns` 互斥
  - `pivot + timeWindow` 互斥
  - `parentShare/baselineRatio` 第一版仅 `axis=rows`
  - 禁止 `expr`
  - 禁止 `CELL_AT` / `AXIS_MEMBER` / `ROLLUP_TO` 公开 DSL
- 运行时先返回明确错误：
  - `PIVOT_NOT_IMPLEMENTED_IN_PYTHON`

验收：

- Pydantic DTO 兼容字符串 metric 和对象 metric。已覆盖。
- Schema 能挡住非法组合。已覆盖合同结构；完整 JSON Schema validator 级互斥测试留到 MCP 网关验收。
- 不执行任何伪 Pivot。已覆盖 `query_model()` 与 `build_query_with_governance()`。

### S2 - Flat Pivot MVP + SQL Parity

状态：已完成。SQLite/MySQL8/Postgres oracle parity 均已验证。

目标：先实现最小可执行 Pivot，覆盖 `outputFormat=flat`。

范围：

- Phase 1 降维：
  - `groupBy = rows + columns`
  - `columns = groupBy + native metrics`
  - metric 聚合读取 TM `aggregation`
- 输出：
  - flat rows
  - `_sys_meta` 预留但只做 data 行
- 权限：
  - `systemSlice` 必须进入 SQL WHERE
  - `deniedColumns` 必须拦截 row/column/metric/property/calculated field 依赖
- SQL parity：
  - SQLite (已验证，`tests/test_dataset_model/test_pivot_v9_flat.py`)
  - MySQL8 (已验证，`tests/integration/test_pivot_v9_flat_real_db_matrix.py`)
  - Postgres (已验证，`tests/integration/test_pivot_v9_flat_real_db_matrix.py`)

验收：

- 基础 rows + metrics 与手写 SQL 结果一致。
- rows + columns + metrics 与手写 SQL 结果一致。
- `slice/systemSlice` 与手写 SQL 结果一致。
- `deniedColumns` 覆盖 Pivot 请求并 fail-closed。
- `pivot + columns`、`pivot + timeWindow` 在运行时继续 fail-closed。

验证：

- `pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/integration/test_pivot_v9_flat_real_db_matrix.py tests/test_mcp/test_query_model_calculate_prompt.py -q`，22 passed。
- `pytest -q`，3828 passed。

### S3 - Grid Shaping + Axis Operations

状态：已完成。SQLite/MySQL8/Postgres grid shaping parity 均已验证。

目标：实现 Java V9 中最常用的前端交叉表能力。

范围：

- `outputFormat=grid`
- rowHeaders / columnHeaders / cells
- axis `having`
- axis `orderBy/limit` 单层和受控 Generate 子集
- `crossjoin`

验收：

- 与 Java `PivotIntegrationTest` snapshot shape 对齐。
- 与 SQL oracle 对比 TopN / having 的成员域（精确比对 headers 与 cells 矩阵数据）。
- crossjoin 补空单元验证（依据 Option A 实现：即使未开启 crossjoin，只要为 grid format 就会由于 2D 数组特性输出 full matrix 包含 None；开启 crossjoin 后会在内存 padding 阶段介入）。

验证：

- `pytest tests/test_dataset_model/test_pivot_v9_contract_shell.py tests/test_dataset_model/test_pivot_v9_flat.py tests/test_dataset_model/test_pivot_v9_grid.py tests/integration/test_pivot_v9_flat_real_db_matrix.py tests/integration/test_pivot_v9_grid_real_db_matrix.py -q`，35 passed。
- `pytest -q`，3842 passed（无任何 regressions，全部 S1/S2/S3 tests 在 SQLite, MySQL8, Postgres 测试用例中 100% 执行并比较 oracle SQL 结果）。

### S4 - Properties + Subtotal + Non-Additive

目标：补齐 V9 财报/BI 核心正确性。

范围：

- `pivot.properties` 后置贴合。
- `rowSubtotals/columnSubtotals/grandTotal`。
- `MetricAdditivityAnalyzer`。
- `RollupCache`。
- non-additive auxiliary query。
- UNION ALL batch + fallback serial。
- 对齐 Java 当前已接受的 oversized surviving domain 安全边界：当 non-additive subtotal/grandTotal 的 surviving domain size `> 500` 时 fail-closed，不静默 fallback。

验收：

- `uniqueCustomers` subtotal 不允许子项求和。
- ratio subtotal 走 recompute/cache。
- oversized domain `> 500` 明确抛出/返回可识别错误，语义与 Java `NonAdditiveRollupDomainTooLargeException` 对齐。
- SQLite/MySQL8/Postgres parity 与手写 SQL 对比。

#### Java Stage 5A Domain Transport 影响决策

Java Stage 5A 是内部执行 spike，用于评估大 surviving domain 的传输形态（例如 `VALUES` CTE、`UNION ALL` CTE、临时表/会话表），不是 Pivot DSL 变更。Python 9.0.0 不应因该 spike 调整外部 JSON schema、request shape 或 result shape。

Python 9.0.0 的默认对齐策略：

- 外部 DSL 不变。
- 先实现当前 Java 已接受语义，而不是追随未默认启用的 Stage 5A prototype。
- non-additive subtotal/grandTotal 遇到 surviving domain size `> 500` 时必须 fail-closed。
- 可增加轻量内部 `DomainTransport` 边界，但前提是不拖慢 S4 主线；默认实现只负责同阈值 fail-closed。
- 若 Java 后续默认启用 Stage 5A transport，Python 将其视为 9.0.x parity enhancement，除非 release owner 明确要求 Python 9.0.0 同步阻断。
- parity snapshot 需要包含 oversized-domain error case，防止未来误改成 silent fallback。

### S5 - Derived Metrics & Tree

目标：覆盖 S11/S12 与父子层级。

范围：

- `parentShare`
- `baselineRatio`
- `hierarchyMode=tree`
- `expandDepth`
- `tree + subtotals` 第一版 fail-closed 或按 Java 已签收口径对齐。

验收：

- parentShare / baselineRatio 三库 SQL parity。
- columns 轴隐式 parentShare fail-closed。
- non-additive guard fail-closed。
- tree shape 与 Java snapshot 对齐。

### S6 - Release Readiness

目标：形成 Python Pivot V9 的发布门禁。

范围：

- `scripts/verify-pivot-v9-python-release.ps1`
- `scripts/verify-pivot-v9-python-release.sh`
- SQLite/MySQL8/Postgres 一键验证。
- Java snapshot consumption。
- Python release signoff 文档。

验收：

- 单命令完成 Python Pivot V9 release readiness。
- 输出明确区分：
  - unit
  - schema
  - SQLite parity
  - MySQL8 parity
  - Postgres parity
  - Java shape snapshot parity

## 优先级建议

第一阶段已经完成强类型契约 + fail-closed shell，第二阶段已经完成 Flat Pivot MVP 与三库 SQL oracle parity，第三阶段已经完成 Grid Shaping + Axis Operations。下一步应进入 S4：Properties + Subtotal + Non-Additive。

原因：

1. `pivot` 合同、Flat/Grid runtime、三库 oracle parity 已经形成基础闭环。
2. S4 是财报/BI 正确性的下一道门槛，尤其是 subtotal/grandTotal 与 non-additive rollup。
3. Java Stage 5A 已明确为内部执行 spike，Python 9.0.0 只需先对齐 `domain > 500` fail-closed 安全边界。
4. S4 完成后，Python 才能进入 parentShare/baselineRatio/tree 等 S5 能力。

推荐下一步：推进 S4 properties/subtotal/non-additive rollup，并继续沿用真实 SQL oracle 对比测试。S4 不碰 parentShare、baselineRatio、tree，也不实现 Java Stage 5A domain transport。

## 当前非目标

- 不把 S2 Flat Pivot 翻译层冒充完整 Pivot Pipeline。
- 不开放通用 `CELL_AT` / `AXIS_MEMBER`。
- 不把 `parentShare` / `baselineRatio` 塞回 `calculatedFields`。
- 不用旧 `withSubtotals` 冒充 V9 Pivot subtotal。
- 不在缺少真实 SQL oracle 的情况下签收后续 Grid/Subtotal/Derived Pivot parity。
