# S6-Phase4 AST Expression Compiler — SQL Predicate Native Compilation

## 文档作用

- doc_type: progress
- intended_for: reviewer
- purpose: 记录 Stage 6 (Phase 4) AST expression compiler 扩展的实际改动与测试证据

## 基本信息

- 对应需求：`docs/v1.5/P2-post-v1.5-followup-execution-plan.md` Stage 6
- 前置交付：`docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-progress.md`
- 状态：`delivered`
- feature flag：`SemanticQueryService(use_ast_expression_compiler=True)`；默认 `False` 不变

## 目标

扩展 Python fsscript parser 和 `FsscriptToSqlVisitor`，原生编译以下 SQL 构造：
- `IS NULL` / `IS NOT NULL`
- `BETWEEN x AND y` / `NOT BETWEEN x AND y`
- `LIKE pattern` / `NOT LIKE pattern`
- `CAST(expr AS type)`

以及保守的 `+` 运算符字符串字面量类型推断（通过方言路由拼接）。

## 开发进度

### 新增 AST 节点

- [x] `src/foggy/fsscript/expressions/sql_predicates.py`（新文件，≈90 行）
  - `IsNullExpression(operand, negated)` — IS [NOT] NULL
  - `BetweenExpression(operand, low, high, negated)` — [NOT] BETWEEN
  - `LikeExpression(operand, pattern, negated)` — [NOT] LIKE
  - `CastExpression(operand, type_name)` — CAST(x AS type)
  - 所有节点 `evaluate()` 抛 `NotImplementedError`（SQL-only，不在 fsscript 运行时执行）

### Parser/Lexer 扩展

- [x] `tokens.py`: 新增 `IS`, `BETWEEN`, `CAST` token types + keywords 映射
- [x] `lexer.py`: `IS`, `BETWEEN` 加入 ASI continuation 令牌（防中缀位断句）
- [x] `parser.py`:
  - PRECEDENCE 表新增 `IS=11`, `BETWEEN=11`
  - `NOT` lookahead 扩展：`NOT BETWEEN` + `NOT LIKE`（复用 `NOT IN` 模式）
  - `_parse_is_rhs()` — IS [NOT] NULL
  - `_parse_between_rhs()` — BETWEEN low AND high
  - `_parse_like_rhs()` — LIKE pattern
  - `_parse_cast()` — CAST(expr AS type) 前缀解析，支持复合类型名（VARCHAR(100)）
- [x] `dialect.py`: `SQL_EXPRESSION_DIALECT` 新增 `"between": None`（formula compiler 用 `between()` 函数调用形态，需解保留）

### Visitor 扩展

- [x] `fsscript_to_sql_visitor.py`:
  - `visit()` 分派新增 4 个节点类型
  - `_visit_is_null()` → `expr IS NULL` / `expr IS NOT NULL`
  - `_visit_between()` → `expr BETWEEN low AND high` / `expr NOT BETWEEN low AND high`
  - `_visit_like()` → `expr LIKE pattern` / `expr NOT LIKE pattern`
  - `_visit_cast()` → `CAST(expr AS type_name)`
  - `+` 运算符类型推断：当任一操作数为 `StringExpression` 时，走 `_dialect_concat()` 路径

### 测试

- [x] `test_ast_expression_compiler.py` — **102 passed**（从 76 增长）
  - `TestSqlPredicates` 22 用例（IS NULL / IS NOT NULL / BETWEEN / NOT BETWEEN / LIKE / NOT LIKE / CAST / CAST precision / 字段解析 / parity / 无回落验证 / IF 组合 / 复合表达式）
  - `TestPlusTypeBehavior` 6 用例（字符串字面量 → 拼接 / 数值 → + / field+string / MySQL 方言路由）
  - `TestFallback` 缩减至 1 用例（仅 EXTRACT 仍走 fallback）
  - 原有用例（Parity / Method / Ternary / Coalesce / Preprocess / Error / E2E）全部保留并通过
- [x] 全量回归 `pytest -q` — **3356 passed, 0 failed**

## 契约对齐证据

### SQL 构造 → AST → SQL 映射

| fsscript 表达式 | AST 节点 | SQL 输出 | 阶段 |
|---|---|---|---|
| `a IS NULL` | `IsNullExpression(negated=False)` | `a IS NULL` | **Stage 6** |
| `a IS NOT NULL` | `IsNullExpression(negated=True)` | `a IS NOT NULL` | **Stage 6** |
| `a BETWEEN x AND y` | `BetweenExpression(negated=False)` | `a BETWEEN x AND y` | **Stage 6** |
| `a NOT BETWEEN x AND y` | `BetweenExpression(negated=True)` | `a NOT BETWEEN x AND y` | **Stage 6** |
| `a LIKE 'x%'` | `LikeExpression(negated=False)` | `a LIKE 'x%'` | **Stage 6** |
| `a NOT LIKE 'x%'` | `LikeExpression(negated=True)` | `a NOT LIKE 'x%'` | **Stage 6** |
| `CAST(a AS INTEGER)` | `CastExpression(type_name='INTEGER')` | `CAST(a AS INTEGER)` | **Stage 6** |
| `'x' + 'y'` | `BinaryExpression(ADD)` → string infer | `'x' \|\| 'y'` (ANSI) / `CONCAT('x', 'y')` (MySQL) | **Stage 6** |

### 仍走回落路径

| 表达式 | 原因 |
|---|---|
| `EXTRACT(YEAR FROM d)` | YEAR() 函数在方言层已有重写，不需 AST 原生支持 |
| 显式 `CASE WHEN ... END` | 已通过 `IF()` 和 ternary `a ? b : c` 覆盖 |

### 兼容性守护

| 约束 | 验证 |
|---|---|
| `use_ast_expression_compiler` 默认 `False` | ✅ `test_default_is_off` |
| formula compiler `between()` 函数调用不受影响 | ✅ `SQL_EXPRESSION_DIALECT` 解保留 + 3 测试通过 |
| 方言字符串拼接路由 | ✅ MySQL CONCAT / Postgres `\|\|` / SQL Server `+` |

## 改动文件清单

### 新增
- `src/foggy/fsscript/expressions/sql_predicates.py`（≈90 行）

### 修改
- `src/foggy/fsscript/parser/tokens.py` — 3 token types + 3 keywords
- `src/foggy/fsscript/parser/lexer.py` — 2 ASI continuation entries
- `src/foggy/fsscript/parser/parser.py` — precedence, NOT lookahead, 4 parse methods, CAST prefix
- `src/foggy/fsscript/parser/dialect.py` — SQL_EXPRESSION_DIALECT `between` 解保留
- `src/foggy/dataset_model/semantic/fsscript_to_sql_visitor.py` — 4 visit methods, + type infer, docstring
- `tests/test_dataset_model/test_ast_expression_compiler.py` — 102 用例（+26 新增）

## 回归基线

- Phase 3 基线：2209 passed（含 76 AST 测试）
- Stage 5 基线：3278 passed
- Stage 6 结果：**3356 passed**（+78 = Stage 5 新增 + Stage 6 26 新 AST 测试）

## v1.5 Java 对齐总览（更新）

| 能力 | Phase 3 | Stage 6 | Java |
|---|:-:|:-:|:-:|
| SQL `IS NULL` / `IS NOT NULL` 走 AST | ❌ (char fallback) | **✅** | ✅ |
| SQL `BETWEEN` / `NOT BETWEEN` 走 AST | ❌ (char fallback) | **✅** | ✅ |
| SQL `LIKE` / `NOT LIKE` 走 AST | ❌ (char fallback) | **✅** | ✅ |
| SQL `CAST(x AS type)` 走 AST | ❌ (char fallback) | **✅** | ✅ |
| `+` 类型推导（字符串拼接） | ❌ | **✅ (保守)** | ✅ |
| AST 覆盖率 | ~85% | **~95%** | 100% |
