# P0 - Python 条件聚合 IF 降级兼容

## 文档作用

- doc_type: `requirement`
- intended_for: `engine-owner | execution-agent | reviewer`
- purpose: 约束 Python 引擎在不升级主 DSL 契约的前提下，对齐 Java `8.1.10-dev` 提交 `4c44918` 的 `sum/avg/count(if(...))` 条件聚合兼容能力

## 基本信息

- 目标版本：`v1.3`
- 优先级：`P0`
- 状态：`resolved`
- 责任项目：`foggy-data-mcp-bridge-python`
- Java 对齐基线：`8.1.10-dev` / `4c44918`

## 背景

Java 侧已支持把 DSL 中的条件聚合写法：

```text
sum(if(cond, 1, 0))
sum(if(cond, amount, 0))
avg(if(cond, amount, null))
count(if(cond, 1, null))
```

稳定降级为标准 SQL `CASE WHEN ... THEN ... ELSE ... END`。

Python 侧此前只支持简单内联聚合 `agg(field)`，对嵌套 `if(...)` 的识别与 SQL lowering 不完整，会导致：

1. `sum/avg/count(if(...))` 无法稳定解析
2. 多数据库下依赖原生 `IF(...)` 的行为不一致
3. `null` 分支存在被 parser / SQL 映射吞掉的风险
4. auto groupBy、orderBy alias、field_access / deniedColumns 等治理链路缺少该场景证据

## 本轮目标

在不引入新 DSL 契约的前提下，对齐 Java 行为：

1. 支持 DSL 中 `sum/avg/count(if(...))`
2. `if(...)` 内等值判断使用 `==`
3. 多条件组合使用 `&&` / `||`
4. SQL 生成阶段统一降级为标准 `CASE WHEN`
5. `null` 分支必须完整保留
6. 不能放宽成任意不稳定表达式

## 明确约束

### 保持不变

1. 不升级 Python 引擎主语法契约
2. 不新增 `count_if / sum_if / avg_if`
3. 不允许用户直接输出原始 `CASE WHEN` DSL
4. 不把能力放宽成任意复杂原生 SQL 片段

### 允许实现方式

1. 函数层识别嵌套 inline aggregate
2. 编译前预处理 / 外围归一化
3. 表达式映射层把 `if(...)` 统一 lowering 到 `CASE WHEN`

## 验收标准

### 1. SQL lowering 语义

以下 DSL 必须分别落成：

```text
sum(if(cond, 1, 0))
-> SUM(CASE WHEN cond THEN 1 ELSE 0 END)

sum(if(cond, measure, 0))
-> SUM(CASE WHEN cond THEN measure ELSE 0 END)

avg(if(cond, measure, null))
-> AVG(CASE WHEN cond THEN measure ELSE NULL END)

count(if(cond, 1, null))
-> COUNT(CASE WHEN cond THEN 1 ELSE NULL END)
```

### 2. 治理链路不回退

以下链路必须保持不受影响：

1. inline aggregate 识别与 auto groupBy
2. orderBy alias
3. join field access
4. field_access 依赖字段校验
5. deniedColumns 黑名单治理
6. metadata/schema 描述对外说明

### 3. 测试证据

至少覆盖：

1. `SUM(IF(cond, 1, 0))`
2. `SUM(IF(cond, measure, 0))`
3. `AVG(IF(cond, measure, NULL))`
4. `COUNT(IF(cond, 1, NULL))`

并满足：

1. 不仅断言 SQL 中包含 `CASE WHEN`
2. 必须在真实数据库执行
3. 必须与手写 native SQL 逐组逐值对账
4. 在当前环境下至少提供 `MySQL + PostgreSQL` 两个真实后端证据

## 非目标

1. 本轮不开放用户直接写 `CASE WHEN`
2. 本轮不引入 `count_if / sum_if / avg_if`
3. 本轮不把 `columns` 放宽到任意复杂 SQL 表达式
4. 本轮不扩展到与本需求无关的表达式契约升级

## 风险关注

1. `calculatedFields` 文档仍保留 `IF` / `CASE` 函数说明，需以后续实现边界继续审视
2. 如果未来扩展到更多表达式类型，仍需继续坚持 fail-closed，避免 parser 放宽导致不稳定 SQL 落地
