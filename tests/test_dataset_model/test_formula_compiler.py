"""Unit tests for FormulaCompiler (M2 Step 2.5).

对齐 Formula Spec v1-r4 (`docs/v1.4/formula-spec-v1/`).
样本清单参考 `examples.md` 78 条（49 正向 + 29 拒绝）。

测试分层：
- TestBasicParsing: 基础 parse + compile 能跑通
- TestArithmetic: 算术（+/-/*/÷/%）
- TestComparison: 比较（==/!=/</>/<=/>=）
- TestLogical: 逻辑（&&/||/!）
- TestLiterals: 字面量（数字/字符串/null/true/false）
- TestInOperator: v in (a, b, c) 运算符
- TestFunctions: 各个白名单函数
- TestAggregation: sum/count/avg/max/min + count(distinct)
- TestDialect: 四方言 date_diff/date_add/now
- TestSecurity: 注入 / DoS / 黑名单拒绝
- TestReq003: REQ-003 业务场景
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.semantic.formula_compiler import (
    CalculateQueryContext,
    CompiledFormula,
    FormulaCompiler,
    FormulaCompilerConfig,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.semantic.field_validator import extract_field_dependencies
from foggy.dataset_model.semantic.formula_errors import (
    FormulaAggNotOutermostError,
    FormulaDepthError,
    FormulaFunctionNotAllowedError,
    FormulaInListSizeError,
    FormulaNodeNotAllowedError,
    FormulaNullComparisonError,
    FormulaSecurityError,
    FormulaSyntaxError,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def passthrough_resolver(name: str) -> str:
    """Test field resolver: 保留字段名原样（不做 table alias）。"""
    return name


@pytest.fixture
def mysql_compiler() -> FormulaCompiler:
    return FormulaCompiler(SqlDialect.of("mysql"))


@pytest.fixture
def pg_compiler() -> FormulaCompiler:
    return FormulaCompiler(SqlDialect.of("postgres"))


@pytest.fixture
def mssql_compiler() -> FormulaCompiler:
    return FormulaCompiler(SqlDialect.of("sqlserver"))


@pytest.fixture
def sqlite_compiler() -> FormulaCompiler:
    return FormulaCompiler(SqlDialect.of("sqlite"))


def _compile(compiler: FormulaCompiler, expr: str) -> CompiledFormula:
    return compiler.compile(expr, passthrough_resolver)


# --------------------------------------------------------------------------- #
# TestBasicParsing
# --------------------------------------------------------------------------- #


class TestBasicParsing:
    """确认基础 parse → compile 链路能跑通。"""

    def test_compile_single_field(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a")
        assert r.sql_fragment == "a"
        assert r.bind_params == ()
        assert r.referenced_fields == frozenset({"a"})

    def test_compile_integer_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "42")
        assert r.sql_fragment == "?"
        assert r.bind_params == (42,)

    def test_compile_string_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "'posted'")
        assert r.sql_fragment == "?"
        assert r.bind_params == ("posted",)

    def test_empty_expression_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "")

    def test_whitespace_only_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "   \t\n")

    def test_non_string_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            mysql_compiler.compile(123, passthrough_resolver)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# TestArithmetic
# --------------------------------------------------------------------------- #


class TestArithmetic:
    """Spec §2.1 算术。"""

    def test_add(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a + b")
        assert r.sql_fragment == "(a + b)"
        assert r.bind_params == ()
        assert r.referenced_fields == frozenset({"a", "b"})

    def test_subtract(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a - b")
        assert r.sql_fragment == "(a - b)"

    def test_multiply_divide(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "(a - b) * 100")
        # Compare to examples.md ari-02
        assert r.sql_fragment == "((a - b) * ?)"
        assert r.bind_params == (100,)

    def test_percentage(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(
            mysql_compiler,
            "(amountTotal - amountResidual) / amountTotal * 100",
        )
        # examples.md ari-03
        assert "/" in r.sql_fragment
        assert "*" in r.sql_fragment
        assert r.bind_params == (100,)

    def test_unary_negate(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "-a")
        assert r.sql_fragment == "(-a)"

    def test_modulo(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a % 2")
        assert r.sql_fragment == "(a % ?)"
        assert r.bind_params == (2,)

    def test_power_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        # Spec §5.1 禁用 **。FSScript parser 本身不接受 `**`
        # （把它识别为两个 `*`），这里 FSScript 层就报 syntax error。
        # 无论哪种都是合理拒绝。
        with pytest.raises((FormulaSyntaxError, FormulaNodeNotAllowedError)):
            _compile(mysql_compiler, "a ** 2")


# --------------------------------------------------------------------------- #
# TestComparison
# --------------------------------------------------------------------------- #


class TestComparison:
    """Spec §2.2 比较。"""

    def test_equal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a == 10")
        assert r.sql_fragment == "(a = ?)"
        assert r.bind_params == (10,)

    def test_not_equal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a != 0")
        assert r.sql_fragment == "(a <> ?)"

    def test_less_than(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a < b")
        assert r.sql_fragment == "(a < b)"

    def test_less_equal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a <= 100")
        assert r.sql_fragment == "(a <= ?)"

    def test_greater_than(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a > 0")
        assert r.sql_fragment == "(a > ?)"

    def test_greater_equal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "a >= 0")
        assert r.sql_fragment == "(a >= ?)"

    def test_null_compare_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaNullComparisonError):
            _compile(mysql_compiler, "a == null")

    def test_null_not_equal_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaNullComparisonError):
            _compile(mysql_compiler, "a != null")


# --------------------------------------------------------------------------- #
# TestLogical
# --------------------------------------------------------------------------- #


class TestLogical:
    """Spec §2.3 逻辑（&&/||/!）。"""

    def test_and(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "(a > 0) && (b < 100)")
        # examples.md bool-01 (r4 adjusted)
        assert "AND" in r.sql_fragment
        assert r.sql_fragment.count("(") == r.sql_fragment.count(")")

    def test_or(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "(a == 0) || (b > 0)")
        assert "OR" in r.sql_fragment

    def test_not(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "!(a == 0)")
        assert r.sql_fragment.startswith("NOT (")


# --------------------------------------------------------------------------- #
# TestLiterals
# --------------------------------------------------------------------------- #


class TestLiterals:
    """Spec §1.1 字面量。"""

    def test_null_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "null")
        assert r.sql_fragment == "NULL"
        assert r.bind_params == ()

    def test_true_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "true")
        assert r.sql_fragment == "?"
        assert r.bind_params == (True,)

    def test_false_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "false")
        assert r.sql_fragment == "?"
        assert r.bind_params == (False,)

    def test_float_literal(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "3.14")
        assert r.sql_fragment == "?"
        assert r.bind_params == (3.14,)


# --------------------------------------------------------------------------- #
# TestInOperator — r4 运算符形式
# --------------------------------------------------------------------------- #


class TestInOperator:
    """Spec §3.2 in / not in 运算符（r4 FSScript 原生支持）。"""

    def test_in_strings(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "state in ('posted', 'paid')")
        assert r.sql_fragment == "(state IN (?, ?))"
        assert r.bind_params == ("posted", "paid")

    def test_in_integers(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "companyId in (1, 2, 3)")
        assert r.sql_fragment == "(companyId IN (?, ?, ?))"
        assert r.bind_params == (1, 2, 3)

    def test_not_in_single_member(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "type not in ('draft')")
        # FSScript 会把单元素 `('draft')` 解析为...可能是 StringExpression 或 ArrayExpression
        # 如果是 StringExpression 则 validator 拒绝（right 不是 ArrayExpression）
        # 预期应该是 ArrayExpression；测试 assert 让我们看实际行为
        assert "NOT IN" in r.sql_fragment

    def test_in_variadic_function_form_rejected(
        self, mysql_compiler: FormulaCompiler,
    ) -> None:
        # examples.md in-07: r3 废除的变参函数形式
        # `in` 是 FSScript 关键字，作为函数名会被 parser 直接拒绝（FormulaSyntaxError）
        with pytest.raises((FormulaSyntaxError, FormulaFunctionNotAllowedError)):
            _compile(mysql_compiler, "in(state, 'posted', 'paid')")


# --------------------------------------------------------------------------- #
# TestFunctions
# --------------------------------------------------------------------------- #


class TestFunctions:
    """Spec §3 函数。"""

    def test_if_basic(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "if(a > 0, a, 0)")
        assert r.sql_fragment == "CASE WHEN ((a > ?)) THEN a ELSE ? END"
        assert r.bind_params == (0, 0)

    def test_if_string_eq(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "if(state == 'posted', 1, 0)")
        assert "CASE WHEN" in r.sql_fragment
        assert r.bind_params == ("posted", 1, 0)

    def test_if_nested(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "if(a > 0, if(b > 0, 1, 2), 3)")
        assert r.sql_fragment.count("CASE WHEN") == 2
        assert r.bind_params == (0, 0, 1, 2, 3)

    def test_if_wrong_arity(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "if(cond, x, y, z)")

    def test_is_null(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "is_null(deletedAt)")
        assert r.sql_fragment == "deletedAt IS NULL"
        assert r.bind_params == ()

    def test_is_not_null(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "is_not_null(confirmedAt)")
        assert r.sql_fragment == "confirmedAt IS NOT NULL"

    def test_coalesce_two_args(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "coalesce(a, 0)")
        assert r.sql_fragment == "COALESCE(a, ?)"
        assert r.bind_params == (0,)

    def test_coalesce_many_args(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "coalesce(a, b, c, 0)")
        assert r.sql_fragment == "COALESCE(a, b, c, ?)"

    def test_abs(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "abs(a - b)")
        assert r.sql_fragment == "ABS((a - b))"

    def test_round(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "round(a, 2)")
        assert r.sql_fragment == "ROUND(a, ?)"
        assert r.bind_params == (2,)

    def test_round_n_out_of_range(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "round(a, 15)")

    def test_round_n_not_literal(self, mysql_compiler: FormulaCompiler) -> None:
        # examples.md num-05
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "round(x, precision)")

    def test_ceil(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "ceil(a / b)")
        assert r.sql_fragment.startswith("CEILING(")

    def test_floor(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "floor(a)")
        assert r.sql_fragment == "FLOOR(a)"

    def test_between(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "between(age, 18, 65)")
        assert r.sql_fragment == "(age BETWEEN ? AND ?)"
        assert r.bind_params == (18, 65)

    def test_unknown_function_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError):
            _compile(mysql_compiler, "substring(x, 1, 3)")


# --------------------------------------------------------------------------- #
# TestAggregation
# --------------------------------------------------------------------------- #


class TestAggregation:
    """Spec §4 聚合 + B-6 distinct pseudo-function。"""

    def test_sum_simple(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "sum(amount)")
        assert r.sql_fragment == "SUM(amount)"

    def test_sum_if(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "sum(if(status == 'cancelled', amount, 0))")
        assert r.sql_fragment.startswith("SUM(CASE WHEN")
        assert r.bind_params == ("cancelled", 0)

    def test_count_if_null(self, mysql_compiler: FormulaCompiler) -> None:
        # examples.md ecom-02: count(if(..., 1, null))
        # parity.md §7: count 包裹下 ELSE NULL 省略
        r = _compile(mysql_compiler, "count(if(amount > 1000, 1, null))")
        assert "COUNT(CASE WHEN" in r.sql_fragment
        # count 不省略 ELSE NULL，只有 count(distinct(...)) 省略
        assert "ELSE NULL" in r.sql_fragment

    def test_avg_if_null(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "avg(if(discountAmount > 0, discountAmount, null))")
        assert r.sql_fragment.startswith("AVG(CASE WHEN")
        assert "ELSE NULL" in r.sql_fragment

    def test_count_distinct(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "count(distinct(buyerId))")
        assert r.sql_fragment == "COUNT(DISTINCT buyerId)"

    def test_count_distinct_if_null(self, mysql_compiler: FormulaCompiler) -> None:
        # parity.md §7: count(distinct(if(..., x, null))) → COUNT(DISTINCT CASE WHEN ... END)
        r = _compile(
            mysql_compiler,
            "count(distinct(if(overdue == true, partnerId, null)))",
        )
        assert r.sql_fragment.startswith("COUNT(DISTINCT CASE WHEN")
        # ELSE NULL 省略
        assert "ELSE NULL" not in r.sql_fragment

    def test_agg_nested_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaAggNotOutermostError):
            _compile(mysql_compiler, "sum(sum(a))")

    def test_agg_inside_if_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        # examples.md agg-02
        with pytest.raises(FormulaAggNotOutermostError):
            _compile(mysql_compiler, "if(cond, sum(a), 0)")

    def test_avg_distinct_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        # examples.md agg-04: avg(distinct(x)) 被拒
        with pytest.raises(FormulaAggNotOutermostError):
            _compile(mysql_compiler, "avg(distinct(x))")

    def test_distinct_standalone_rejected(
        self, mysql_compiler: FormulaCompiler,
    ) -> None:
        # examples.md agg-05: distinct(x) + 1 被拒
        with pytest.raises((FormulaAggNotOutermostError, FormulaFunctionNotAllowedError)):
            _compile(mysql_compiler, "distinct(x) + 1")

    def test_unknown_agg_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        # examples.md agg-03: median(a) 被拒
        with pytest.raises(FormulaFunctionNotAllowedError):
            _compile(mysql_compiler, "median(a)")


# --------------------------------------------------------------------------- #
# TestDialect — 方言特化（date_diff / date_add / now）
# --------------------------------------------------------------------------- #


class TestDialect:
    """Spec §6.2 date_diff / date_add / now 方言分派。"""

    def test_now_mysql(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "now()")
        assert r.sql_fragment == "NOW()"

    def test_now_mssql(self, mssql_compiler: FormulaCompiler) -> None:
        r = _compile(mssql_compiler, "now()")
        assert r.sql_fragment == "GETDATE()"

    def test_now_sqlite(self, sqlite_compiler: FormulaCompiler) -> None:
        r = _compile(sqlite_compiler, "now()")
        assert r.sql_fragment == "datetime('now')"

    def test_date_diff_mysql(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "date_diff(now(), dateMaturity)")
        assert r.sql_fragment == "DATEDIFF(NOW(), dateMaturity)"

    def test_date_diff_pg(self, pg_compiler: FormulaCompiler) -> None:
        r = _compile(pg_compiler, "date_diff(now(), dateMaturity)")
        assert r.sql_fragment == "(NOW()::date - dateMaturity::date)"

    def test_date_diff_mssql(self, mssql_compiler: FormulaCompiler) -> None:
        r = _compile(mssql_compiler, "date_diff(now(), dateMaturity)")
        assert r.sql_fragment == "DATEDIFF(day, dateMaturity, GETDATE())"

    def test_date_diff_sqlite(self, sqlite_compiler: FormulaCompiler) -> None:
        r = _compile(sqlite_compiler, "date_diff(now(), dateMaturity)")
        assert "julianday" in r.sql_fragment

    def test_date_add_mysql(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "date_add(today, 30, 'day')")
        assert r.sql_fragment == "DATE_ADD(today, INTERVAL ? DAY)"
        assert r.bind_params == (30,)

    def test_date_add_pg(self, pg_compiler: FormulaCompiler) -> None:
        r = _compile(pg_compiler, "date_add(today, 30, 'day')")
        assert r.sql_fragment == "(today + make_interval(days => ?))"
        assert r.bind_params == (30,)

    def test_date_add_unit_invalid(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "date_add(today, 30, 'hour')")

    def test_date_diff_wrong_arity(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSyntaxError):
            _compile(mysql_compiler, "date_diff(a, b, c)")


# --------------------------------------------------------------------------- #
# TestSecurity
# --------------------------------------------------------------------------- #


class TestSecurity:
    """examples.md §11 安全拒绝 + §7 硬上限。"""

    def test_eval_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaFunctionNotAllowedError):
            _compile(mysql_compiler, "eval('x')")

    def test_dunder_identifier_rejected(self, mysql_compiler: FormulaCompiler) -> None:
        with pytest.raises(FormulaSecurityError):
            _compile(mysql_compiler, "a + __class__")

    def test_injection_attempt_as_string(
        self, mysql_compiler: FormulaCompiler,
    ) -> None:
        """SQL 注入字符串作为字面量：
        - Parser 接受（合法字符串）
        - SQL 里字符串走 bind_params（只包含 `?`）
        - 验证：SQL 片段里**不含** DROP/SEMICOLON 等危险字符
        """
        r = _compile(mysql_compiler, "'1); DROP TABLE users; --'")
        assert r.sql_fragment == "?"
        assert r.bind_params == ("1); DROP TABLE users; --",)
        assert "DROP" not in r.sql_fragment
        assert ";" not in r.sql_fragment

    def test_expression_too_long(self, mysql_compiler: FormulaCompiler) -> None:
        expr = "a" + " + a" * 2000  # 远超 4096 字符
        with pytest.raises(FormulaSecurityError):
            _compile(mysql_compiler, expr)

    def test_in_list_too_large(self) -> None:
        # 1025 个整数成员字符串约 6KB，超过默认 max_expr_len=4096
        # 临时放宽 max_expr_len 以验证 IN 成员数硬上限
        compiler = FormulaCompiler(
            SqlDialect.of("mysql"),
            config=FormulaCompilerConfig(max_expr_len=100_000),
        )
        members = ", ".join(str(i) for i in range(1025))
        with pytest.raises(FormulaInListSizeError):
            compiler.compile(f"id in ({members})", passthrough_resolver)

    def test_depth_limit(self) -> None:
        """嵌套深度超限拒绝。默认 max_depth=32；构造 40 层 if 嵌套。"""
        compiler = FormulaCompiler(SqlDialect.of("mysql"))
        # 构造 if(cond, if(cond, if(..., 40 层), 0), 0)
        expr = "1"
        for _ in range(40):
            expr = f"if(true, {expr}, 0)"
        with pytest.raises(FormulaDepthError):
            compiler.compile(expr, passthrough_resolver)

    def test_depth_limit_configurable(self) -> None:
        """降低 max_depth 应该更早拒绝。

        FSScript AST 深度计算：每层 `if(cond, a, b)` 增深 1 层；4 层嵌套
        `if(true, if(true, if(true, if(true, 1, 0), 0), 0), 0)` 深度 = 5。
        设 max_depth=3，4 层嵌套应超限。
        """
        compiler = FormulaCompiler(
            SqlDialect.of("mysql"),
            config=FormulaCompilerConfig(max_depth=3),
        )
        with pytest.raises(FormulaDepthError):
            compiler.compile(
                "if(true, if(true, if(true, if(true, 1, 0), 0), 0), 0)",
                passthrough_resolver,
            )


# --------------------------------------------------------------------------- #
# TestReq003 — REQ-003 业务样本 smoke test
# --------------------------------------------------------------------------- #


class TestReq003:
    """examples.md §10 REQ-003 L1b measure。烟测，验证能 compile 不抛错。"""

    def test_ar_outstanding(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(
            mysql_compiler,
            "sum(if(moveType == 'out_invoice' && state == 'posted' "
            "&& paymentState in ('not_paid', 'partial', 'in_payment'), "
            "amountResidual, 0))",
        )
        assert r.sql_fragment.startswith("SUM(CASE WHEN")
        # 检查关键参数都在
        assert "out_invoice" in r.bind_params
        assert "posted" in r.bind_params
        assert "not_paid" in r.bind_params

    def test_ar_overdue_customer_count(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(
            mysql_compiler,
            "count(distinct(if("
            "moveType == 'out_invoice' && state == 'posted' "
            "&& paymentState in ('not_paid', 'partial') "
            "&& date_diff(now(), dateMaturity) > 0, "
            "partnerId, null)))",
        )
        assert r.sql_fragment.startswith("COUNT(DISTINCT CASE WHEN")
        # ELSE NULL 省略
        assert "ELSE NULL" not in r.sql_fragment

    def test_won_amount(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(
            mysql_compiler,
            "sum(if(is_not_null(stageIsWon) && stageIsWon, expectedRevenue, 0))",
        )
        assert r.sql_fragment.startswith("SUM(CASE WHEN")


# --------------------------------------------------------------------------- #
# TestCalculateMvp — v1.5.1 P1 restricted CALCULATE MVP
# --------------------------------------------------------------------------- #


class TestCalculateMvp:
    def _resolver(self, name: str) -> str:
        return {
            "salesAmount": "t.sales_amount",
            "customer$customerType": "d3.customer_type",
            "product$categoryName": "d2.category_name",
        }.get(name, name)

    def _compile(
        self,
        compiler: FormulaCompiler,
        expr: str,
        ctx: CalculateQueryContext,
    ) -> CompiledFormula:
        return compiler.compile(expr, self._resolver, calculate_context=ctx)

    def test_remove_all_group_by_lowers_to_global_window(
        self,
        sqlite_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            supports_grouped_aggregate_window=True,
        )
        result = self._compile(
            sqlite_compiler,
            "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
            "REMOVE(customer$customerType)), 0)",
            ctx,
        )

        assert result.sql_fragment == (
            "(SUM(t.sales_amount) / "
            "NULLIF(SUM(SUM(t.sales_amount)) OVER (), 0))"
        )
        assert result.bind_params == ()
        assert result.referenced_fields == frozenset({"salesAmount"})

    def test_remove_one_group_by_keeps_remaining_partition(
        self,
        sqlite_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType", "product$categoryName"),
            supports_grouped_aggregate_window=True,
        )
        result = self._compile(
            sqlite_compiler,
            "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
            "REMOVE(product$categoryName)), 0)",
            ctx,
        )

        assert result.sql_fragment == (
            "(SUM(t.sales_amount) / NULLIF(SUM(SUM(t.sales_amount)) "
            "OVER (PARTITION BY d3.customer_type), 0))"
        )
        assert result.referenced_fields == frozenset(
            {"salesAmount", "customer$customerType"}
        )

    def test_scalar_wrapper_around_calculate_ratio_is_allowed(
        self,
        sqlite_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            supports_grouped_aggregate_window=True,
        )
        result = self._compile(
            sqlite_compiler,
            "ROUND(SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
            "REMOVE(customer$customerType)), 0), 4)",
            ctx,
        )

        assert result.sql_fragment == (
            "ROUND((SUM(t.sales_amount) / "
            "NULLIF(SUM(SUM(t.sales_amount)) OVER (), 0)), ?)"
        )
        assert result.bind_params == (4,)

    @pytest.mark.parametrize(
        ("expr", "message"),
        [
            (
                "SUM(salesAmount) / CALCULATE(SUM(salesAmount), "
                "REMOVE(customer$customerType))",
                "CALCULATE_RATIO_REQUIRES_NULLIF",
            ),
            (
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                "REMOVE(product$categoryName)), 0)",
                "CALCULATE_REMOVE_FIELD_NOT_GROUPED",
            ),
            (
                "SUM(salesAmount) / NULLIF(CALCULATE(AVG(salesAmount), "
                "REMOVE(customer$customerType)), 0)",
                "CALCULATE_EXPR_UNSUPPORTED",
            ),
            (
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                "REMOVE(customer$customerType + 1)), 0)",
                "CALCULATE_REMOVE_FIELD_NOT_GROUPED",
            ),
            (
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(CALCULATE("
                "SUM(salesAmount), REMOVE(customer$customerType))), "
                "REMOVE(customer$customerType)), 0)",
                "CALCULATE_NESTED_UNSUPPORTED",
            ),
        ],
    )
    def test_restricted_calculate_rejections(
        self,
        sqlite_compiler: FormulaCompiler,
        expr: str,
        message: str,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            supports_grouped_aggregate_window=True,
        )

        with pytest.raises(FormulaSyntaxError, match=message):
            self._compile(sqlite_compiler, expr, ctx)

    def test_remove_system_slice_field_is_denied(
        self,
        sqlite_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            system_slice_fields=frozenset({"customer"}),
            supports_grouped_aggregate_window=True,
        )

        with pytest.raises(
            FormulaSyntaxError,
            match="CALCULATE_SYSTEM_SLICE_OVERRIDE_DENIED",
        ):
            self._compile(
                sqlite_compiler,
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                "REMOVE(customer$customerType)), 0)",
                ctx,
            )

    def test_mysql_window_support_is_explicitly_rejected(
        self,
        mysql_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            supports_grouped_aggregate_window=False,
        )

        with pytest.raises(FormulaSyntaxError, match="CALCULATE_WINDOW_UNSUPPORTED"):
            self._compile(
                mysql_compiler,
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                "REMOVE(customer$customerType)), 0)",
                ctx,
            )

    def test_time_window_post_calculate_is_rejected(
        self,
        sqlite_compiler: FormulaCompiler,
    ) -> None:
        ctx = CalculateQueryContext(
            group_by_fields=("customer$customerType",),
            supports_grouped_aggregate_window=True,
            time_window_post_calculated_fields=True,
        )

        with pytest.raises(
            FormulaSyntaxError,
            match="CALCULATE_TIMEWINDOW_POST_CALC_UNSUPPORTED",
        ):
            self._compile(
                sqlite_compiler,
                "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
                "REMOVE(customer$customerType)), 0)",
                ctx,
            )

    def test_dependency_extraction_includes_remove_fields_for_governance(self) -> None:
        deps = extract_field_dependencies(
            "SUM(salesAmount) / NULLIF(CALCULATE(SUM(salesAmount), "
            "REMOVE(customer$customerType)), 0)"
        )

        assert deps == {"salesAmount", "customer$customerType"}


# --------------------------------------------------------------------------- #
# TestEcommerce — 非 REQ-003 通用样本（R-5）
# --------------------------------------------------------------------------- #


class TestEcommerce:
    """examples.md §10.5 非 REQ-003 通用业务样本。"""

    def test_net_amount(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "salesAmount - discountAmount")
        assert r.sql_fragment == "(salesAmount - discountAmount)"

    def test_cancelled_orders_amount(self, mysql_compiler: FormulaCompiler) -> None:
        r = _compile(mysql_compiler, "sum(if(status == 'cancelled', amount, 0))")
        assert r.sql_fragment.startswith("SUM(CASE WHEN")
        assert r.bind_params == ("cancelled", 0)


# --------------------------------------------------------------------------- #
# Note (r5, 2026-04-20): The former `TestIfIifPreprocessing` class verified
# the `if → IIF` character-state-machine preprocessor that has now been
# replaced by FsscriptDialect (Scanner-level keyword override). The 12
# preprocessing edge cases moved to:
#
#     tests/test_fsscript/test_dialect.py
#         · TestSqlExpressionDialect — `if(...)` parses as function call
#         · TestNaturalProtections   — string literal / word-boundary safety
#                                       inherited for free from the lexer
#
# IIF as a public alias is intentionally retired; users always write `if(...)`
# in formula expressions, and the dialect layer makes that legal natively.
# --------------------------------------------------------------------------- #
