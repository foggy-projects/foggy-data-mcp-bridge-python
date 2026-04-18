# P0 - Python 条件聚合 IF 降级兼容 - Progress

## 文档作用

- doc_type: `progress`
- intended_for: `engine-owner | execution-agent | reviewer`
- purpose: 回写 Python 引擎条件聚合 IF 降级兼容的实现、测试与数据库对账证据

## 基本信息

- 目标版本：`v1.3`
- 优先级：`P0`
- 状态：`implemented`
- 责任项目：`foggy-data-mcp-bridge-python`
- 上游需求：`docs/v1.3/P0-Python条件聚合IF降级兼容-需求.md`
- Java 对齐基线：`8.1.10-dev` / `4c44918`

## 改动清单

### 代码

1. `src/foggy/dataset_model/semantic/inline_expression.py`
   - 新增 nested inline aggregate 解析器，支持 `sum(if(...))`
2. `src/foggy/dataset_model/semantic/service.py`
   - 递归表达式 lowering
   - `IF(...) -> CASE WHEN ... THEN ... ELSE ... END`
   - `==` / `&&` / `||` SQL 化
   - `NULL` 分支保留
3. `src/foggy/dataset_model/service/facade.py`
   - inline aggregate 检测从正则升级为结构化解析，保证 auto groupBy 仍能识别嵌套 `if(...)`

### 测试

1. `tests/test_dataset_model/test_inline_expression.py`
   - 覆盖四类 SQL lowering
   - 覆盖多条件与 join field access
2. `tests/test_dataset_model/test_query_facade.py`
   - 覆盖 nested inline aggregate 检测与 auto groupBy
3. `tests/test_dataset_model/test_conditional_aggregate_if_alignment.py`
   - SQLite 对账样例
   - field_access / deniedColumns / orderBy alias 治理证据
   - MySQL / PostgreSQL 真实数据库逐组逐值对账

### MCP / schema 描述

1. `src/foggy/mcp/schemas/descriptions/query_model_v3.md`
2. `src/foggy/mcp/schemas/descriptions/query_model_v3_no_vector.md`
3. `src/foggy/mcp/schemas/descriptions/query_model_v3_basic.md`

已补齐：

1. `sum/avg/count(if(...))` 示例
2. `==` / `&&` / `||` 约束
3. `IF -> CASE WHEN` lowering 说明
4. 不支持 raw `CASE WHEN`
5. 不新增 `count_if / sum_if / avg_if`

## 实现说明

### 1. inline aggregate 识别

原先正则只能处理 `agg(field)` 这类简单表达式，无法稳定识别 `sum(if(...))`。

本轮改为：

1. 先结构化解析聚合函数与最外层括号
2. 支持嵌套函数参数
3. `facade.py` 与 `service.py` 共用同一解析器

### 2. IF lowering

表达式渲染阶段按 token 递归处理：

1. `==` -> `=`
2. `&&` -> `AND`
3. `||` -> `OR`
4. `IF(a, b, c)` -> `CASE WHEN a THEN b ELSE c END`

其中 `NULL` 作为 SQL keyword 保留，不会被字段解析吞掉。

### 3. 治理链路

已补证据证明以下链路未回退：

1. auto groupBy
2. orderBy alias
3. field_access 依赖字段校验
4. deniedColumns 黑名单校验
5. join field access

## 数据库范围

### 真实后端

1. MySQL
   - host: `localhost:13306`
   - database: `foggy_test`
   - user: `foggy`
2. PostgreSQL
   - host: `localhost:15432`
   - database: `foggy_test`
   - user: `foggy`

### 对账场景

1. `SUM(IF(cond, 1, 0))`
2. `SUM(IF(cond, measure, 0))`
3. `AVG(IF(cond, measure, NULL))`
4. `COUNT(IF(cond, 1, NULL))`

对账口径：

1. 先跑 DSL 查询
2. 再跑手写 native SQL
3. 按 `orderStatus` 分组逐组逐值比对

## 待回写测试结果

执行命令：

```powershell
pytest tests/test_dataset_model/test_inline_expression.py tests/test_dataset_model/test_query_facade.py tests/test_dataset_model/test_conditional_aggregate_if_alignment.py -q
```

执行后在本文件补充：

1. 通过数
2. MySQL 对账结果
3. PostgreSQL 对账结果
4. 残余差异与风险
