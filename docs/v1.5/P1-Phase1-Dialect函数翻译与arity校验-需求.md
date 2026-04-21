# P1-Phase1 Dialect 函数翻译与 arity 校验-需求

## 文档作用

- doc_type: workitem
- intended_for: execution-agent
- purpose: 在不改变 `_render_expression` 架构的前提下，把"跨方言函数翻译"和"函数 arity 校验"两项 Java 已有的能力补齐到 Python

## 基本信息

- 版本：`v1.5`
- Phase：1 / 3
- 等级：`P1`
- 状态：`signed-off`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase1-Dialect函数翻译与arity校验-acceptance.md
- blocking_items: none
- follow_up_required: no
- 交付模式：`single-root-delivery`
- 对应 Java：
  - `foggy-dataset/src/main/java/.../db/dialect/PostgresDialect.java#buildFunctionCall`
  - `foggy-dataset/src/main/java/.../db/dialect/SqliteDialect.java#buildFunctionCall`
  - `foggy-dataset/src/main/java/.../db/dialect/SqlServerDialect.java#buildFunctionCall`
  - `foggy-dataset-model/src/test/java/.../DialectFunctionTranslationTest.java`

## 背景

Python 侧 `FDialect.translate_function(func_name, args)` 已存在（`src/foggy/dataset/dialects/base.py:113-134`），但：

1. **没有被 `_render_expression` 调用** —— 计算字段 → SQL 的字符级翻译器直接输出 `FUNC_NAME(args)`，完全绕过方言
2. `_get_function_mappings` 只覆盖简单重命名（`IFNULL ↔ COALESCE/ISNULL` 等），无法表达 `DATE_FORMAT(col, fmt)` → `TO_CHAR(col, translated_fmt)` 这种需要**参数位置重排和格式串翻译**的 case
3. 没有函数 arity 校验（除 `IF`），写错参数数量会到 SQL 执行期才报错，错误信息不友好

## 目标

### Scope-in

1. 在 `FDialect` 基类新增 `build_function_call(func_name, args) -> Optional[str]`
   - 返回完整 SQL 调用串，或 `None` 表示"默认处理"（即走 `translate_function` 重命名 + 模板）
2. 各方言实现（对齐 Java）：
   - **PostgresDialect**：
     - `YEAR/MONTH/DAY/HOUR/MINUTE/SECOND(col)` → `EXTRACT(YEAR FROM col)` 等
     - `DATE_FORMAT(col, '%Y-%m')` → `TO_CHAR(col, 'YYYY-MM')`（含 MySQL 日期格式串→Postgres 格式串的字典翻译）
   - **SqliteDialect**：
     - `YEAR(col)` → `CAST(strftime('%Y', col) AS INTEGER)` 等
     - `DATE_FORMAT(col, fmt)` → `strftime(fmt, col)` （参数顺序反转）
   - **SqlServerDialect**：
     - `HOUR/MINUTE/SECOND(col)` → `DATEPART(HOUR, col)` 等（`YEAR/MONTH/DAY` 为原生）
     - `DATE_FORMAT(col, '%Y-%m')` → `FORMAT(col, 'yyyy-MM')`（含 MySQL→SQL Server 格式串翻译）
     - 统计函数：`STDDEV_POP/SAMP` → `STDEVP/STDEV`，`VAR_POP/SAMP` → `VARP/VAR`
     - `SUBSTR` → `SUBSTRING`，`CEIL` → `CEILING`，`CHAR_LENGTH` → `LEN`
   - **MysqlDialect**：`TRUNC` → `TRUNCATE`，`POW` → `POWER`（+现有已覆盖的 IFNULL/ISNULL/NVL）
3. 扩展各方言 `_get_function_mappings` 覆盖剩余简单重命名
4. 把 `_render_expression` 的函数调用分支改成：优先走 `dialect.build_function_call`，`None` 时走 `dialect.translate_function`，方言未配置时维持现有行为
5. 新增 `_FUNCTION_ARITY` 表，对 `_render_expression` 遇到的每个函数调用校验实际参数数量
6. 友好错误信息：`"Function 'ROUND' expects 1-2 arguments, got 4"`
7. 镜像 Java `DialectFunctionTranslationTest.java` 的核心测试用例到 Python pytest

### Scope-out（明确延后）

- ❌ 计算字段依赖图 / 循环检测 → **Phase 2**
- ❌ AST-based 重构 → **Phase 3**
- ❌ fsscript 方法调用 `s.startsWith(x)` → **Phase 3**
- ❌ `+` 运算符的字符串/数值类型推导 → **Phase 3**
- ❌ MySQL 5.7 vs 8+ 的 CTE / window / JSON 差异（已有 `supports_cte` 等覆盖，不扩）

## 设计约束

### 向后兼容

- 当方言的 `build_function_call` 返回 `None` 且 `_get_function_mappings` 没命中时，**输出与旧 `_render_expression` 完全一致**
- 如果 `SemanticQueryService` 的 `_dialect` 是 `None`（某些测试路径），继续走旧路径，不崩

### 错误语义

- 参数数错：在**编译期**抛 `ValueError`（不是运行期），错误信息含函数名、允许范围、实际值
- 未知函数：继续由现有 `_ALLOWED_FUNCTIONS` 白名单拒绝（不变）
- 方言无法翻译某个函数（`build_function_call` 和 `_get_function_mappings` 都未命中）：默认按 `FUNC_NAME(args)` 原样输出，与旧行为一致

### 日期格式串翻译

提供两张查找表（对齐 Java `translateMysqlDateFormat` / `translateMysqlDateFormatToSqlServer`）：

**MySQL → Postgres**（出现在字符串字面量里）：
```
%Y → YYYY    %y → YY
%m → MM      %d → DD
%H → HH24    %i → MI    %s → SS
%M → Month   %b → Mon
%W → Day     %a → Dy
%j → DDD
```

**MySQL → SQL Server**：
```
%Y → yyyy    %y → yy
%m → MM      %d → dd
%H → HH      %i → mm    %s → ss
```

翻译范围：仅替换 `%X` 占位符；字符串其他部分（连字符、空格、中文、标点）原样保留。

## 任务拆分

### 1. 基础设施（`foggy/dataset/dialects/`）

| 文件 | 改动 |
|---|---|
| `base.py` | 新增 `build_function_call(func_name, args) -> Optional[str]` 返回 `None`（默认实现） |
| `base.py` | `translate_function` 内部先试 `build_function_call`，命中即返回；否则走现有 `_get_function_mappings` 路径 |
| `postgres.py` | 实现 `build_function_call`（YEAR/MONTH/DAY/HOUR/MINUTE/SECOND → EXTRACT，DATE_FORMAT → TO_CHAR）+ `_translate_mysql_date_format_to_postgres` 辅助函数 |
| `sqlite.py` | 实现 `build_function_call`（YEAR/…/SECOND → CAST(strftime(...) AS INTEGER)，DATE_FORMAT → strftime 反参） |
| `sqlserver.py` | 实现 `build_function_call`（HOUR/MINUTE/SECOND → DATEPART，DATE_FORMAT → FORMAT）+ `_translate_mysql_date_format_to_sqlserver`；补充 `_get_function_mappings`：STDDEV_* / VAR_* / SUBSTR / CEIL / CHAR_LENGTH |
| `mysql.py` | 补 `_get_function_mappings`：TRUNC → TRUNCATE，POW → POWER |

### 2. 计算字段编译器（`foggy/dataset_model/semantic/service.py`）

| 改动位置 | 内容 |
|---|---|
| class `SemanticQueryService` | 新增 `_FUNCTION_ARITY` 字典（见下文） |
| `_render_expression` lines 957-983 | 在识别到函数调用后、组装输出前：① 从 `_FUNCTION_ARITY` 校验实参个数；② 递归渲染每个参数；③ 如果 `self._dialect` 非空，调用 `self._dialect.build_function_call(func_name, rendered_args)`；命中即用，未命中再调 `self._dialect.translate_function(func_name, rendered_args)`；均未命中回落现有 `f"{func_name}({args})"` |
| `_FUNCTION_ARITY` | 覆盖全部 `_ALLOWED_FUNCTIONS` 成员；值 `(min_args, max_args_or_None)`；CAST / EXTRACT / CONVERT 因含 `AS`/`FROM` 关键字做参数分隔不准，**不纳入 arity 校验**（仍由白名单把关） |

### 3. 测试

新文件：`tests/test_dataset_model/test_dialect_function_translation.py`

对齐 Java `DialectFunctionTranslationTest.java`。覆盖：

- 每方言的 `translate_function` 简单重命名（IFNULL / NVL / ISNULL / POW / TRUNC / CEIL / SUBSTR / LENGTH / CHAR_LENGTH）
- 每方言的 `build_function_call` 复杂翻译（YEAR/MONTH/DAY/HOUR/MINUTE/SECOND / DATE_FORMAT）
- DATE_FORMAT 格式串翻译：MySQL 字符 → Postgres / SQL Server
- 端到端：通过 `SemanticQueryService._resolve_expression_fields` 验证方言感知的 SQL 输出

新文件：`tests/test_dataset_model/test_function_arity_validation.py`

- 正确参数数量：IF(a,b,c)、ROUND(x)、ROUND(x,2)、COALESCE(a,b,c)、CONCAT(a,b,c,d) 全通过
- 参数不足：ROUND() / IF(a) 抛 `ValueError`，消息含"expects 1-2 arguments, got 0"
- 参数过多：ROUND(a,b,c,d) 抛 `ValueError`，消息含"got 4"
- 不校验项：CAST(x AS INT)、EXTRACT(YEAR FROM d) 不抛错

## 验收标准

- [ ] 所有方言的 `build_function_call` 输出与 Java 对应 dialect 输出一致（至少 15 个对照用例）
- [ ] arity 校验覆盖 `_ALLOWED_FUNCTIONS` 全部（除显式排除项 CAST/EXTRACT/CONVERT），至少 20 条正面 + 10 条负面 case
- [ ] 端到端：`status in ('a','b')` 在 Postgres 方言下渲染为 `t.status IN('a', 'b')`（已工作，防止退化）；`DATE_FORMAT(d, '%Y-%m')` 在 Postgres 方言下渲染为 `TO_CHAR(t.d, 'YYYY-MM')`
- [ ] 回归：现有 `tests/` 全量 0 失败；基线 1905 → 1905+N（N = Phase 1 新增）
- [ ] 所有 Dialect 实例单独实例化后 `build_function_call(None, None)` 与 `build_function_call("NOT_A_FUNC", [])` 不崩
- [ ] `SemanticQueryService(dialect=None)` 路径（无方言）维持现有 SQL 输出一致

## 非目标

- 不重写 `_render_expression` 架构
- 不新增 `FsscriptToSqlVisitor`
- 不修计算字段间依赖 / 循环
- 不把方言层暴露给 DSL/MCP 外部用户（仅内部翻译使用）

## Progress Tracking

### 开发进度

- [x] 1. `FDialect.build_function_call` base + `translate_function` 改造
- [x] 2. PostgresDialect：EXTRACT 日期函数族 + DATE_FORMAT → TO_CHAR + 格式串翻译
- [x] 3. SqliteDialect：strftime 日期函数族 + DATE_FORMAT 参数反转
- [x] 4. SqlServerDialect：DATEPART + FORMAT + STDEV/VARP + SUBSTRING/CEILING/LEN 重命名
- [x] 5. MysqlDialect：TRUNC 补充重命名（POW 保留 native，对齐 Java）
- [x] 6. `SemanticQueryService._render_expression` 集成 dialect
- [x] 7. `_FUNCTION_ARITY` 表 + 编译期校验

### 测试进度

- [x] `test_dialect_function_translation.py` 83 passed
- [x] `test_function_arity_validation.py` 99 passed
- [x] 全量回归 `pytest -q` 2087 passed, 0 failed

### 执行 Checkin

详见 `P1-Phase1-Dialect函数翻译与arity校验-progress.md`。
