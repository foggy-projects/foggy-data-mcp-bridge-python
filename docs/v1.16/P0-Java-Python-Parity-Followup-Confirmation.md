# P0 Java/Python 对齐后续项确认

## 文档作用

- 文档类型：工作项
- 状态：待确认
- 面向对象：产品负责人 / 总控 Agent / Python 引擎执行 Agent / Java 引擎执行 Agent / 评审人
- 用途：将 v1.15 对齐基线中剩余的测试和功能缺口分配到合适迭代，供后续逐项确认。

## 版本信息

- 版本：v1.16
- 优先级：P0 规划 / 确认
- 来源类型：验收后续项
- 归属仓库：`foggy-data-mcp-bridge-python`
- Java 参考仓库：`foggy-data-mcp-bridge-wt-dev-compose`

## 背景

v1.15 已确认：Python 引擎与 Java 引擎在当前已签收的公开能力和运行时能力范围内对齐。剩余项不是当前缺陷，而是后续是否扩大支持范围的确认问题。

本文件的目标是避免后续执行时混淆三类事情：

- 只需要补测试证据的项。
- 需要先做语义设计的项。
- 当前应继续拒绝或延期的项。

## 后续项总表

| ID | 问题 | 建议迭代 | 当前边界 | 需要确认的问题 |
|---|---|---|---|---|
| JP-FU-01 | CALCULATE 的 SQL Server oracle | v1.16 P1 | Python CALCULATE 已签 SQLite/MySQL8/PostgreSQL；SQL Server 尚未作为显式支持声明 | 是否要把 SQL Server CALCULATE 升级为公开对齐能力？ |
| JP-FU-02 | stable relation 的 join / union 作为后续 source | v1.16 P2 | 当前只签收 outer aggregate/window | 是否有真实业务需要把 join/union relation 作为后续 relation source？ |
| JP-FU-03 | Pivot SQL Server cascade oracle | v1.17 P1 | Java/Python 均拒绝或延期 | 是否要实现 SQL Server staged cascade renderer，还是继续拒绝？ |
| JP-FU-04 | Pivot MySQL 5.7 live evidence | v1.17 P2 | Java/Python 均不继承 MySQL8 证据 | 是否仍支持 MySQL 5.7，还是明确从 cascade/domain transport 支持范围移除？ |
| JP-FU-05 | tree+cascade 语义规格 | v1.18 P1 | Java/Python 均拒绝或延期 | 是否要投入语义设计，定义可证明的 tree ranking / subtotal / visible domain 规则？ |
| JP-FU-06 | outer Pivot cache | v1.19 P1 | 仅完成可行性评估，无 runtime cache | 是否有生产 telemetry 证明缓存收益足以覆盖权限安全和失效复杂度？ |

## 分项说明

### JP-FU-01 CALCULATE 的 SQL Server Oracle

建议迭代：v1.16 P1。

当前状态：

- Python v1.11 已签收受限形态：`CALCULATE(SUM(metric), REMOVE(dim))`。
- 现有 oracle 矩阵覆盖 SQLite、MySQL8、PostgreSQL。
- SQL Server 的 timeWindow 和 stable relation outer 已有证据，但 CALCULATE SQL Server 尚未签收为支持声明。

可选决策：

- `accept-evidence-work`：为受限 CALCULATE 增加 SQL Server 真实数据库 oracle 测试。
- `defer`：保持当前支持声明不变。
- `reject`：明确 SQL Server CALCULATE 不属于公开对齐范围。

如果确认推进，需要补的测试：

- SQL Server 全局占比场景的 grouped aggregate window oracle。
- SQL Server 分区占比场景的 grouped aggregate window oracle。
- SQL Server 对嵌套 CALCULATE、移除非 groupBy 字段等不支持场景的拒绝测试。
- 新增测试后的全量回归。

非目标：

- 不扩展到受限 CALCULATE 之外。
- 不支持嵌套 CALCULATE 或任意 MDX 坐标漫游。

### JP-FU-02 stable relation 的 join / union 作为后续 source

建议迭代：v1.16 P2。

当前状态：

- Python v1.12-v1.14 已签收 stable relation outer aggregate/window runtime。
- 已签收范围不包含 stable relation join/union 作为后续 source。

可选决策：

- `require-design`：实现前先编写 dedicated stable relation source 设计文档。
- `defer`：保持 outer aggregate/window 为唯一签收 runtime path。
- `reject`：明确 join/union relation source 不在范围内。

如果确认推进，需要补的测试：

- SQLite/MySQL8/PostgreSQL/SQL Server 的 join source oracle。
- SQLite/MySQL8/PostgreSQL/SQL Server 的 union source oracle。
- `systemSlice`、`deniedColumns`、`fieldAccess`、masking 的权限传递测试。
- 嵌套 relation 层级下的 SQL sanitizer 和参数顺序测试。

非目标：

- 不提供 raw SQL escape hatch。
- 不绕过 compose/queryModel authority envelope。

### JP-FU-03 Pivot SQL Server Cascade Oracle

建议迭代：v1.17 P1。

当前状态：

- Java 9.1 / 9.2 将 SQL Server cascade 标记为拒绝或延期。
- Python v1.10 已签收 SQL Server cascade 拒绝路径。

可选决策：

- `align-with-java-implementation`：仅在 Java 接受 SQL Server oracle 后再开始 Python 镜像。
- `python-prototype`：Python 可先做 renderer 原型，但在 Java/产品签收前不声明 parity。
- `continue-refusal`：继续保持稳定的 `PIVOT_CASCADE_SQL_REQUIRED` 拒绝。

如果确认推进，需要补的测试：

- SQL Server 两级 rows cascade oracle。
- 父级排序不受子级 limit 影响。
- 父级 having 先于子级 ranking。
- 子级 having 不影响父级 ranking。
- 确定性的 NULL tie-breaking。
- surviving domain 上的 additive subtotal/grandTotal。
- tree、cross-axis、three-level、non-additive 等不支持场景继续 fail-closed。

非目标：

- 不允许 cascade 退回内存 fallback。
- 不支持通用 MDX Generate。

### JP-FU-04 Pivot MySQL 5.7 Live Evidence

建议迭代：v1.17 P2。

当前状态：

- Java 将 MySQL 5.7 记录为受保护的 fail-closed 路径或 live evidence 缺口。
- Python v1.10 已签收显式 MySQL5.7 拒绝测试。

可选决策：

- `live-refusal-evidence`：增加真实 MySQL5.7 fixture，证明稳定拒绝。
- `support-limited-transport`：仅在语义允许时设计非 window fallback。
- `drop-support`：将 MySQL5.7 明确记录为不支持 cascade/domain transport。

如果确认推进，需要补的测试：

- 真实 MySQL5.7 下 cascade 在 SQL 执行前拒绝。
- 真实 MySQL5.7 下 large-domain transport 拒绝或 limited transport oracle。
- MySQL8 回归测试，证明不会被 MySQL5.7 策略误伤。

非目标：

- 没有签收算法前，不模拟 MySQL8 window 语义。
- 不基于 executor class 把 MySQL5.7 误标为 MySQL8。

### JP-FU-05 tree+cascade 语义规格

建议迭代：v1.18 P1。

当前状态：

- Java 和 Python 当前都拒绝 tree+cascade。
- Python v1.10 已完成语义评审和 runtime 拒绝，但没有实现。

可选决策：

- `semantic-design`：定义 tree ranking、visible nodes、descendant aggregation、subtotal behavior 和 oracle matrix。
- `defer`：继续保持 fail-closed。
- `reject`：明确 tree+cascade 不属于 Pivot DSL 设计范围。

如果确认推进，需要补的测试：

- 父子可见域 oracle。
- 隐藏 descendants 下的 ranking。
- tree subtotal 是基于 visible domain 还是 full descendant domain 的决策测试。
- 跨方言 SQL oracle，或明确的不支持方言拒绝测试。
- 非 cascade tree 行为的兼容性测试。

非目标：

- 语义签收前不实现。
- 不用 best-effort tree flattening 代替真实语义。

### JP-FU-06 outer Pivot Cache

建议迭代：v1.19 P1。

当前状态：

- Java 9.2 将 outer Pivot cache 标记为延期项。
- Python v1.10 可行性结论是：在 telemetry 和权限安全 cache key 签收前，不增加 runtime cache。

可选决策：

- `telemetry-first`：先收集查询耗时和重复请求证据，再决定是否实现。
- `design-cache-key`：先定义权限安全 cache key 和失效模型。
- `defer`：继续不做 outer cache。

如果确认推进，需要补的测试：

- cache key 必须包含 model、pivot request、用户可见权限、`systemSlice`、`deniedColumns`、dialect 和相关模型版本。
- cache 不得跨 authority envelope 泄漏数据。
- 模型或 schema 变化后的失效测试。
- hit/miss telemetry 测试。
- 实现前后的性能基线。

非目标：

- 不允许只按原始 request JSON 做 cache key。
- 不允许忽略权限或 system slice。

## 责任归属

| 领域 | 主负责人 | 协同负责人 |
|---|---|---|
| CALCULATE SQL Server oracle | Python 引擎 | Java 对齐评审 |
| stable relation join/union source | Python 引擎 / compose owner | governance 评审 |
| Pivot SQL Server cascade | Java Pivot 优先，随后 Python 镜像 | dialect owner |
| Pivot MySQL5.7 evidence | dialect owner | Python/Java 引擎负责人 |
| tree+cascade 语义规格 | 产品 / 语义 owner | Java/Python Pivot owner |
| outer Pivot cache | 性能 / cache owner | governance 评审 |

## 验收标准

- 每个条目都有明确决策：`accepted-for-implementation`、`evidence-only`、`deferred` 或 `rejected`。
- 任何进入实现的条目，都必须有独立 requirement、implementation plan、progress tracker、quality gate、coverage audit 和 acceptance record。
- 任何延期或拒绝的条目，都必须保持稳定 fail-closed 行为，公开文档不能声明支持。
- 任何条目都不能在没有单独产品批准的情况下改变 public DSL。

## 进度跟踪

开发进度：

| 步骤 | 状态 | 说明 |
|---|---|---|
| 创建后续项 intake 文档 | 已完成 | v1.16 docs created. |
| 确认 JP-FU-01 | 待确认 | 等待产品/工程决策。 |
| 确认 JP-FU-02 | 待确认 | 等待产品/工程决策。 |
| 确认 JP-FU-03 | 待确认 | 依赖 Java/Product 对 SQL Server cascade 的决策。 |
| 确认 JP-FU-04 | 待确认 | 依赖 MySQL5.7 支持策略。 |
| 确认 JP-FU-05 | 待确认 | 需要语义评审。 |
| 确认 JP-FU-06 | 待确认 | 需要 telemetry / performance 信号。 |

测试进度：

| 范围 | 状态 | 说明 |
|---|---|---|
| 当前 v1.15 回归 | 已通过 | `pytest -q` -> `3977 passed`。 |
| 新 runtime 测试 | 不适用 | 本文档仅规划确认，不新增 runtime 代码。 |
| 后续逐项 oracle 测试 | 待确认 | 已在各条目下列出。 |

体验进度：

- 不适用。这些都是后端/query-engine 规划项，没有 UI 流程。

## 约束 / 非目标

- 不能仅凭本文档直接开始实现。
- 在条目被接受并完成测试前，不改变 MCP schema 或公开 prompt 声明。
- 不把拒绝/延期项改成静默 fallback。
- 没有可执行 oracle 或明确拒绝证据时，不声明某个方言具备 Java/Python parity。

## 必要评审流程

每个条目如果要从确认阶段进入后续阶段，必须按以下顺序推进：

1. 生成独立 requirement / plan 文档包。
2. 使用 `plan-evaluator` 评审。
3. 评审通过后再执行实现。
4. 执行 `foggy-implementation-quality-gate`。
5. 执行 `foggy-test-coverage-audit`。
6. 执行 `foggy-acceptance-signoff`。
