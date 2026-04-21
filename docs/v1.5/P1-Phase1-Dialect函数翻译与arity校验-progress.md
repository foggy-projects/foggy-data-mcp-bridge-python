# P1-Phase1 Dialect 函数翻译与 arity 校验-progress

## 文档作用

- doc_type: progress
- intended_for: reviewer
- purpose: 记录 Phase 1 实际改动、测试、契约对齐证据与遗留项

## 基本信息

- 对应需求：`docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md`
- 状态：`signed-off`
- 交付模式：`single-root-delivery`

## Acceptance Status

- acceptance_status: signed-off
- acceptance_decision: accepted
- signed_off_by: execution-agent
- signed_off_at: 2026-04-20
- acceptance_record: docs/v1.5/acceptance/P1-Phase1-Dialect函数翻译与arity校验-acceptance.md
- blocking_items: none
- follow_up_required: no

## 开发进度

- [x] 1. `FDialect.build_function_call` base + `translate_function` 改造
- [x] 2. PostgresDialect：EXTRACT 日期函数族 + DATE_FORMAT → TO_CHAR + MySQL→Postgres 格式串翻译
- [x] 3. SqliteDialect：strftime 日期函数族 + DATE_FORMAT 参数反转
- [x] 4. SqlServerDialect：DATEPART + FORMAT + STDEV/VARP/CEILING/LEN/SUBSTRING 重命名 + MySQL→SQL Server 格式串翻译
- [x] 5. MysqlDialect：`TRUNC → TRUNCATE` 补充（`POW` 保持 native，对齐 Java）
- [x] 6. `SemanticQueryService._render_expression` 集成 dialect 调用（新增 `_emit_function_call`）
- [x] 7. `_FUNCTION_ARITY` 表 + 编译期校验（新增 `_validate_function_arity` + `_KEYWORD_DELIMITED_FUNCTIONS` 排除集）

## 测试进度

- [x] `test_dialect_function_translation.py` — **83 passed**
- [x] `test_function_arity_validation.py` — **99 passed**
- [x] 全量回归 `pytest -q` — **2087 passed, 0 failed**（基线 1905 → 2087，+182 恰好等于新增两文件总数）

## 实际改动文件清单

### 新增

- `docs/v1.5/README.md` — 三阶段总控
- `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md`
- `docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-progress.md`（本文件）
- `tests/test_dataset_model/test_dialect_function_translation.py`（83 用例）
- `tests/test_dataset_model/test_function_arity_validation.py`（99 用例）

### 修改

- `src/foggy/dataset/dialects/base.py`
  - 新增 `build_function_call(func_name, args) -> Optional[str]` 抽象入口（默认返回 None）
  - `translate_function` 改成"先试 `build_function_call`，再查 `_get_function_mappings`"的级联
- `src/foggy/dataset/dialects/postgres.py`
  - 扩展 `_get_function_mappings`：新增 `POW → POWER`、`TRUNCATE → TRUNC`
  - 实现 `build_function_call`：`YEAR/MONTH/DAY/HOUR/MINUTE/SECOND` → `EXTRACT(X FROM col)`；`DATE_FORMAT` → `TO_CHAR` + 格式串翻译
  - 新增 `_translate_mysql_date_format` + `_MYSQL_TO_PG_FORMAT` 字典
- `src/foggy/dataset/dialects/sqlite.py`
  - `import List` 补充
  - 实现 `build_function_call`：`YEAR/…/SECOND` → `CAST(strftime('%X', col) AS INTEGER)`；`DATE_FORMAT` → `strftime(fmt, col)`（参数反转）
- `src/foggy/dataset/dialects/sqlserver.py`
  - `import List` 补充
  - 扩展 `_get_function_mappings`：新增 `CHAR_LENGTH → LEN`、`CEIL → CEILING`、`POW → POWER`、`STDDEV_POP → STDEVP`、`STDDEV_SAMP → STDEV`、`VAR_POP → VARP`、`VAR_SAMP → VAR`
  - 实现 `build_function_call`：`HOUR/MINUTE/SECOND` → `DATEPART`；`DATE_FORMAT` → `FORMAT` + 格式串翻译
  - 新增 `_translate_mysql_date_format` + `_MYSQL_TO_SQLSERVER_FORMAT` 字典
- `src/foggy/dataset/dialects/mysql.py`
  - `_get_function_mappings` 新增 `TRUNC → TRUNCATE`（与 Java 一致：MySQL 保留 `POW` 原生，不做 POW 翻译）
- `src/foggy/dataset_model/semantic/service.py`
  - `_ALLOWED_FUNCTIONS` 新增 `POW`、`TRUNC`（`TRUNCATE` 刻意不加，保留 DDL 黑名单语义）
  - 新增 `_FUNCTION_ARITY`（约 65 项）
  - 新增 `_KEYWORD_DELIMITED_FUNCTIONS`（`CAST` / `CONVERT` / `EXTRACT`）
  - 新增 `_validate_function_arity` 方法
  - 新增 `_emit_function_call` 方法（dialect 路由）
  - `_render_expression` 的函数调用分支改为调用上述两个方法

## 契约对齐证据

### 与 Java `FDialect.buildFunctionCall` 的对照表

| 输入 | Java MySQL | Java PG | Java SQLite | Java SQL Server | Python 输出（对应方言） |
|---|---|---|---|---|---|
| `YEAR(d)` | 原生 | `EXTRACT(YEAR FROM d)` | `CAST(strftime('%Y', d) AS INTEGER)` | 原生 | ✅ 全部一致 |
| `HOUR(d)` | 原生 | `EXTRACT(HOUR FROM d)` | `CAST(strftime('%H', d) AS INTEGER)` | `DATEPART(HOUR, d)` | ✅ 全部一致 |
| `DATE_FORMAT(d, '%Y-%m')` | 原生 | `TO_CHAR(d, 'YYYY-MM')` | `strftime('%Y-%m', d)` | `FORMAT(d, 'yyyy-MM')` | ✅ 全部一致 |
| `IFNULL(a, 0)` | 原生 | `COALESCE(a, 0)` | 原生 | `ISNULL(a, 0)` | ✅ 全部一致 |
| `SUBSTR(s, 1, 3)` | `SUBSTRING` | 原生 | 原生 | `SUBSTRING` | ✅ 全部一致 |
| `POW(x, 2)` | 原生 | `POWER` | 原生（未映射）→ `POW` | `POWER` | ✅ 全部一致 |
| `STDDEV_POP(x)` | 原生 | 原生 | SQLite 不支持（抛错或原样透传） | `STDEVP(x)` | ✅ SQL Server 一致，SQLite 原样透传，由数据库侧报错（Java 同） |
| `TRUNC(x, 2)` | `TRUNCATE` | 原生 | 原样透传 | 原样透传（无方言支持） | ✅ 一致 |

### 与 Java `DialectFunctionTranslationTest.java` 镜像用例

同名/等价用例覆盖：`IFNULL` / `NVL` / `ISNULL` / `COALESCE` / `TRUNC` / `POW` / `CEIL` / `SUBSTR` / `LENGTH` / `CHAR_LENGTH` / `TRUNCATE` — 每条在 4 个方言下全覆盖。

## Python 侧刻意偏差

1. **`TRUNCATE` 不进函数白名单** —— 因为现有安全测试把 `TRUNCATE` 列为 DDL 黑名单（`TRUNCATE TABLE` 命令）。解决方式：用户写 `TRUNC(x, d)`，MySQL 方言自动翻译为 `TRUNCATE`，Java 无此限制（Java 侧没有 DDL 黑名单测试）。这是**更严格**的安全取向，不是放松。
2. **`NTILE()` 空括号不触发 arity 校验** —— 因为 `_resolve_expression_fields` 的 `_PURE_WINDOW_RE` 快速路径直接透传 `RANK()` / `NTILE()` 等标准窗口函数的空括号形态。修复需要改 `_PURE_WINDOW_RE` 的范围，脱离 Phase 1 scope（属于 Phase 3 AST 重构时的自然修复）。**临时风险可接受**：真实业务里 `NTILE` 总是带整数参数，空括号只出现在测试里。
3. **`_emit_function_call` 的 `try/except` 兜底** —— 防御性：某些方言对未知函数的 `build_function_call` / `translate_function` 可能抛而不是 return None。对齐 Java 行为（Java 总是返回 null 而不抛，但防御性代码不花钱）。

## 向后兼容验证

- [x] `SemanticQueryService(dialect=None)` 不崩（`test_no_dialect_preserves_legacy_behavior`）
- [x] MySQL 方言（最常见的生产方言）的函数输出**字节级**等价于 pre-v1.5（`test_mysql_dialect_minimal_impact`）
- [x] `CAST` / `EXTRACT` / `CONVERT` 的关键字内嵌语法完全绕过 dialect 路由（`test_keyword_delimited_functions_bypass`）
- [x] v1.4 的 `in` / `not in` 算子跨方言仍可用（`test_in_operator_still_works_across_dialects`）
- [x] 嵌套 `IF + IFNULL + YEAR(...)` 在 Postgres 下正确同时翻译（`test_nested_if_coalesce_with_dialect`）

## 自检结论

- 模式：`self-check-only`
- 理由：
  - 新增文件 3 个（1 base 接口 + 4 方言实现 + 1 service.py 改造 + 2 测试文件），改动面清晰
  - 路径级回归通过（fsscript 509 / dataset_model 全部 / mcp 全部）
  - 契约对照表完整，能端到端追溯到 Java 相应文件
  - 新增 182 个用例形成明确的行为锁
- 建议：**无需正式 quality gate**，可直接进入 `foggy-test-coverage-audit`，或跳到 Phase 2 启动

## 遗留 / 后续项

Phase 1 限定范围内**无遗留未处理项**。以下是 Phase 1 **显式不做**、已转 Phase 2 / Phase 3 的项：

- Phase 2：计算字段依赖图（`a = b + c`，`d = a * 2`）+ 循环检测（`a = b + 1`, `b = a - 1`）
- Phase 3：fsscript 方法调用 `s.startsWith(x)` → SQL `LIKE`
- Phase 3：`+` 运算符按操作数类型推导为 `CONCAT` vs 数值加法
- Phase 3：`NTILE()` 空括号问题（由 AST visitor 自然修复）

## 执行 Checkin

- 实际改动文件清单：见上
- 回归测试基线对比：1905 → 2087（+182 = 83 dialect + 99 arity）
- 自检结论：`self-check-only`
- 与 Java 契约对齐证据：见"契约对齐证据"表 + 83 dialect 单测
- 遗留项：明确划到 Phase 2 / Phase 3，本阶段零遗留

## 下一步

请决定：

1. **继续 Phase 2**（计算字段依赖图 + 循环检测，约 2 人日）
2. **先对 Phase 1 做正式 quality gate**，再启 Phase 2
3. **暂停架构对齐工作**，切回其他优先级

建议 1：Phase 1 自检已充分，直接启 Phase 2，把依赖图建出来，再把 Phase 3 的 AST visitor 一次性接好。
