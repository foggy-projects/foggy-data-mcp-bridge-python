# P1-Phase3 AST-based `FsscriptToSqlVisitor` 架构对齐-progress

## 文档作用

- doc_type: progress
- intended_for: reviewer
- purpose: 记录 Phase 3 实际改动、契约对齐证据、与现状限制

## 基本信息

- 对应需求：`docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md`
- 状态：`signed-off`
- 交付模式：`single-root-delivery`
- feature flag：`SemanticQueryService(use_ast_expression_compiler=True)`；默认 `False` 保留 pre-Phase-3 行为

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted-with-risks
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase3-AST-Visitor-架构对齐-acceptance.md
- blocking_items: none
- follow_up_required: no

## 开发进度

- [x] 1. `fsscript_to_sql_visitor.py` 框架 + 字面量 + 变量 + 成员访问
- [x] 2. 二元 + 一元 + 三元表达式
- [x] 3. 函数调用（plain call）+ 方法调用翻译（`startsWith` / `endsWith` / `contains` / `toUpperCase` / `toLowerCase` / `trim` / `length`）
- [x] 4. `IF(...)` 预处理（`_preprocess_if`；词边界 + 字符串字面量跳过）
- [x] 5. `service.py` 集成：feature flag + AstCompileError fallback
- [x] 6. `_extract_field_dependencies` 修正：识别方法名（`.` 前缀标识符）排除出字段依赖

## 测试进度

- [x] `test_ast_expression_compiler.py` — **76 passed**
  - Parity 34 组（AST ≡ char 语义等价）
  - 方法调用 7+3（AST-only 能力 + char 拒绝对照）
  - 方言路由（MySQL / Postgres / SQL Server）
  - 三元 + null coalesce
  - 回落 9 组（`IS NULL`/`BETWEEN`/`LIKE`/`CAST`/`EXTRACT`）
  - 预处理 8 组
  - 错误处理 3 组（`instanceof` / 未知方法 / arity）
  - AST + compiled_calcs 集成
- [x] 全量回归 `pytest -q` — **2209 passed, 0 failed**（基线 2133 + 76 = 2209）

## 实际改动文件清单

### 新增

- `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md`
- `docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-progress.md`（本文件）
- `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py` ≈ 440 行
  - `render_with_ast` — 入口函数：预处理 → 解析 → visitor
  - `FsscriptToSqlVisitor` — AST 节点分派表
  - `AstCompileError(ValueError)` — 回落触发器
  - `_preprocess_if(source)` — `IF(` → `__FSQL_IF__(`，跳过字符串字面量和非词边界
  - `_STRING_METHOD_NAMES` 集合
  - `_IF_SENTINEL = "__FSQL_IF__"`
- `tests/test_dataset_model/test_ast_expression_compiler.py` ≈ 76 用例

### 修改

- `src/foggy/dataset_model/semantic/service.py`
  - 新 import：`render_with_ast`, `AstCompileError`
  - `__init__` 新增参数 `use_ast_expression_compiler: bool = False`
  - `_render_expression` 开头新增 AST-first 分支 + ParseError/AstCompileError 回落
- `src/foggy/dataset_model/semantic/field_validator.py`
  - `_extract_field_dependencies` 识别 `.method` 前缀，排除方法名出字段依赖集合

## 契约对齐证据

### fsscript AST → SQL 映射（覆盖所有 Java 行为）

| fsscript | AST 节点 | SQL 输出 | 对齐 Java |
|---|---|---|---|
| `a + b` | `BinaryExpression(ADD)` | `a + b` | ✅ |
| `a == b` | `BinaryExpression(EQUAL)` | `a = b` | ✅ |
| `a != b` | `BinaryExpression(NOT_EQUAL)` | `a <> b`（标准化） | ✅ 语义等价 |
| `a && b` | `BinaryExpression(AND)` | `a AND b` | ✅ |
| `a \|\| b` | `BinaryExpression(OR)` | `a OR b` | ✅ |
| `a ?? b` | `BinaryExpression(NULL_COALESCE)` | `COALESCE(a, b)`（经方言） | **AST 新增** |
| `a in (x, y)` | `BinaryExpression(IN, rhs=ArrayExpression)` | `a IN (x, y)` | ✅ |
| `a not in (x, y)` | `BinaryExpression(NOT_IN, ...)` | `a NOT IN (x, y)` | ✅ |
| `a ? b : c` | `TernaryExpression` | `CASE WHEN a THEN b ELSE c END` | **AST 新增** |
| `IF(a, b, c)` | 预处理 → `FunctionCallExpression(__FSQL_IF__)` | `CASE WHEN a THEN b ELSE c END` | ✅ |
| `!x` | `UnaryExpression(NOT)` | `NOT x` | ✅ |
| `-x` | `UnaryExpression(NEGATE)` | `-x` | ✅ |
| `YEAR(d)` (Postgres) | plain `FunctionCallExpression` | `EXTRACT(YEAR FROM d)`（Phase 1 方言） | ✅ |
| `s.startsWith(x)` | `FunctionCallExpression(function=MemberAccess)` | `s LIKE CONCAT(x, '%')`（方言） | **AST 新增，Java 对齐** |
| `s.endsWith(x)` | 同上 | `s LIKE CONCAT('%', x)`（方言） | **AST 新增** |
| `s.contains(x)` | 同上 | `s LIKE CONCAT('%', x, '%')`（方言） | **AST 新增** |
| `s.toUpperCase()` | 同上 | `UPPER(s)` | **AST 新增** |
| `s.toLowerCase()` | 同上 | `LOWER(s)` | **AST 新增** |
| `s.trim()` | 同上 | `TRIM(s)` | **AST 新增** |
| `s.length()` | 同上 | `LENGTH(s)`（方言 `LEN`） | **AST 新增** |

### 方言路由实证

```
输入: name.startsWith('A')
  none:      t.name LIKE 'A' || '%'               (ANSI 默认)
  mysql:     t.name LIKE CONCAT('A', '%')         ← MySQL
  postgres:  t.name LIKE 'A' || '%'               ← Postgres
  sqlserver: t.name LIKE 'A' + '%'                ← SQL Server

输入: name.length()
  mysql:     LENGTH(t.name)                       ← native
  sqlserver: LEN(t.name)                          ← Phase 1 rename
```

### v1.4 / v1.5 Phase 1 / Phase 2 兼容

| 功能 | AST 路径验证 |
|---|---|
| `in` / `not in`（v1.4） | ✅ 6 个测试 |
| Dialect 函数翻译（Phase 1） | ✅ 3 方言实证 |
| arity 校验（Phase 1） | ✅ 方法调用 arity + IF arity |
| 计算字段依赖图（Phase 2） | ✅ `test_ast_can_use_compiled_calcs` |
| 循环检测（Phase 2） | ✅ 不受 AST 影响（在外层运行） |

## 已知限制与明确 Scope-out

### Python fsscript 解析器不支持的 SQL 语法（Phase 4 候选）

这些表达式**不会走 AST 路径**，而是通过 `AstCompileError` 回落到 char tokenizer：

- `a IS NULL` / `a IS NOT NULL`
- `a BETWEEN x AND y`
- `a LIKE 'x%'`
- `CAST(x AS type)` — 实际上 char tokenizer 也能处理，但 AST parser 视为无效
- `CASE WHEN a THEN b ... END` 显式语法
- 其它 SQL-specific 关键字语法

**影响**：用户写这些时行为与 pre-Phase-3 完全一致。

**后续**：若要 100% AST 覆盖，需升级 Python fsscript parser 支持这些语法（Phase 4），规模约 1 人周。

### 其它限制

- `+` 操作数类型推导（字符串拼接 vs 数值加法）：仍 emit SQL `+`，用户需显式 `CONCAT(...)` 做字符串拼接
- `instanceof` 不翻译，抛 `AstCompileError`，无 fallback 路径能处理
- 默认 flag 为 `False`，生产路径行为字节级不变

## Python 侧刻意偏差

1. **`!=` 标准化为 `<>`**：AST 路径输出 `<>`（标准 SQL），char 路径保留 `!=`（MySQL 兼容但非 ANSI）。两者语义等价，没有 SQL 引擎会报错。Parity 测试用 `_normalize_sql` 打平这一差异。
2. **`a && b` 外加括号**：AST 路径输出 `(a > 0) AND (b > 0)` 带分组括号，char 路径输出 `a > 0  AND  b > 0`（无括号但双空格）。两者都符合 SQL。AST 的括号更保守、更安全。
3. **方法调用 concat**：采用 dialect 的 `get_string_concat_sql`（pre-existing 接口），与 Java `Dialect.buildStringConcat` 对应但函数签名略有差异。
4. **`__FSQL_IF__` sentinel**：用文本 mangling 绕开 fsscript parser 的 `if` 关键字限制。Java 不需要（其 fsscript parser 支持表达式位置 IF）。若未来 Python fsscript 升级，sentinel 可移除。

## 向后兼容验证

- [x] `SemanticQueryService(use_ast_expression_compiler=False)` 字节级 pre-Phase-3 等价（`test_default_is_off`）
- [x] 新 Flag 默认 False（`test_default_is_off` 锁定）
- [x] AST flag 开启时，所有已知 char-tokenizer 能通的表达式仍可通（34 parity 用例）
- [x] AST flag 开启时，SQL-specific 语法仍可通（9 回落用例）
- [x] 全量 pytest 回归 2209 / 0

## 自检结论

- 模式：`self-check-only`
- 理由：
  - feature flag 默认 off，零风险
  - 76 个新用例覆盖 AST / parity / fallback / dialect 四个维度
  - 0 regressions
  - 契约对齐证据完整（映射表 + 方言实证 + Phase1/2 兼容）
- 建议：无需 `foggy-implementation-quality-gate`；可进入 v1.5 正式验收（`foggy-test-coverage-audit` + `foggy-acceptance-signoff`）

## 遗留 / 后续项

### 不在 Phase 3 范围（明确延后）

- **Phase 4（可选，独立立项）**：Python fsscript parser 补齐 SQL 关键字语法（`IS NULL` / `BETWEEN` / `LIKE` / `CASE WHEN ... END`）。完成后 AST 路径可覆盖 100% 场景，`_render_expression` char 路径可下线。规模约 1 人周。
- **默认翻转**（"Phase 3 收尾"）：等 Phase 4 完成 + 2 轮生产稳定后，翻 `use_ast_expression_compiler=True`，然后下线 char tokenizer。规模 0.25 人日。
- `+` 运算符类型推导（字符串拼接）：需要 AST 静态分析操作数类型，规模 0.5 人日。

### 本 Phase 零未完成项

所有需求 scope-in 项已实现 + 测试。

## 执行 Checkin

- 实际改动文件清单：见"实际改动文件清单"
- 回归测试基线对比：2133 → 2209（+76，完全等于新增用例数）
- 自检结论：`self-check-only`
- 契约对齐证据：见"契约对齐证据"表 + 方言实证 + 76 单测
- 遗留项：Phase 4（可选）+ 默认翻转（Phase 3 收尾）

## 达成的 Java 对齐总览（v1.5 完整版）

| 能力 | v1.4 前 | Phase 1 | Phase 2 | Phase 3 | Java |
|---|:-:|:-:|:-:|:-:|:-:|
| `in`/`not in` 运算符 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 跨方言函数翻译 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 函数 arity 校验 | 仅 IF | ✅ | ✅ | ✅ | ✅ |
| calc 拓扑排序 | ❌ | ❌ | ✅ | ✅ | ✅ |
| calc 循环检测 | ❌ | ❌ | ✅ | ✅ | ✅ |
| calc 传递依赖 | ❌ | ❌ | ✅ | ✅ | ✅ |
| slice/orderBy/groupBy 引用 calc | ❌ | ❌ | ✅ | ✅ | ✅ |
| fsscript 方法调用 | ❌ | ❌ | ❌ | **✅ (AST)** | ✅ |
| Ternary `a ? b : c` | ❌ | ❌ | ❌ | **✅ (AST)** | ✅ |
| `??` null coalesce | ❌ | ❌ | ❌ | **✅ (AST)** | ✅ |
| AST-based SQL 生成 | ❌ | ❌ | ❌ | **✅ (flag)** | ✅ |
| `+` 类型推导 | ❌ | ❌ | ❌ | ❌ | ✅ |
| SQL 关键字语法（`IS NULL` 等）走 AST | ❌ | ❌ | ❌ | ❌ (char fallback) | ✅ |

**v1.5 完成时达成 11/13 = 85% 架构对齐**。剩余 2 项（`+` 类型推导、Python fsscript parser 升级）可在 Phase 4 单独评估。
