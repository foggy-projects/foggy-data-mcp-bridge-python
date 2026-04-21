"""Tests for calculated fields (DbFormulaDef) — aligned with Java CalculatedFieldTest
and CalculatedFieldAggregationBugTest."""

import sqlite3

import pytest

from foggy.dataset_model.definitions.measure import DbFormulaDef, FormulaOperator
from foggy.dataset_model.semantic.formula_compiler import (
    CompiledFormula,
    FormulaCompiler,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_formula(expression: str, **kwargs) -> DbFormulaDef:
    """Create a DbFormulaDef with sensible defaults."""
    return DbFormulaDef(name=kwargs.pop("name", "test_formula"), expression=expression, **kwargs)


# ===========================================================================
# TestDbFormulaDef — evaluate() tests
# ===========================================================================

class TestDbFormulaDef:
    """Tests for DbFormulaDef.evaluate() using safe AST-based evaluation."""

    # -- basic arithmetic ---------------------------------------------------

    def test_simple_arithmetic(self):
        formula = _make_formula("salesAmount - discountAmount")
        result = formula.evaluate({"salesAmount": 100, "discountAmount": 20})
        assert result == 80.0

    def test_multiplication(self):
        formula = _make_formula("unitPrice * quantity")
        result = formula.evaluate({"unitPrice": 10.5, "quantity": 3})
        assert result == pytest.approx(31.5)

    def test_division(self):
        formula = _make_formula("profitAmount / salesAmount * 100")
        result = formula.evaluate({"profitAmount": 30, "salesAmount": 100})
        assert result == pytest.approx(30.0)

    def test_division_by_zero(self):
        """Division by zero should return None (exception handled)."""
        formula = _make_formula("a / b")
        result = formula.evaluate({"a": 10, "b": 0})
        assert result is None

    def test_complex_expression(self):
        formula = _make_formula("(salesAmount - discountAmount) * 0.9")
        result = formula.evaluate({"salesAmount": 100, "discountAmount": 20})
        assert result == pytest.approx(72.0)

    def test_nested_parentheses(self):
        formula = _make_formula("((a + b) * (c - d)) / e")
        result = formula.evaluate({"a": 2, "b": 3, "c": 10, "d": 4, "e": 5})
        # ((2+3) * (10-4)) / 5 = (5 * 6) / 5 = 6.0
        assert result == pytest.approx(6.0)

    def test_unary_minus(self):
        formula = _make_formula("-a + b")
        result = formula.evaluate({"a": 3, "b": 10})
        assert result == pytest.approx(7.0)

    def test_power(self):
        formula = _make_formula("a ** 2")
        result = formula.evaluate({"a": 5})
        assert result == pytest.approx(25.0)

    def test_floor_div(self):
        formula = _make_formula("a // b")
        result = formula.evaluate({"a": 7, "b": 2})
        assert result == pytest.approx(3.0)

    def test_modulo(self):
        formula = _make_formula("a % b")
        result = formula.evaluate({"a": 7, "b": 3})
        assert result == pytest.approx(1.0)

    # -- edge cases ---------------------------------------------------------

    def test_unknown_variable(self):
        """Unknown variable should cause evaluate() to return None."""
        formula = _make_formula("unknown + 1")
        result = formula.evaluate({"a": 10})
        assert result is None

    def test_unsafe_expression_blocked(self):
        """Unsafe code-injection expression must NOT execute; returns None."""
        formula = _make_formula("__import__('os').system('rm -rf /')")
        result = formula.evaluate({})
        assert result is None

    def test_non_numeric_ignored(self):
        """String values in the dict should be filtered out (only numerics kept)."""
        formula = _make_formula("a + b")
        result = formula.evaluate({"a": 10, "b": "not_a_number"})
        # 'b' is filtered out → unknown variable → None
        assert result is None

    def test_numeric_with_string_mix(self):
        """When the expression only uses numeric keys, strings are silently ignored."""
        formula = _make_formula("a + 1")
        result = formula.evaluate({"a": 5, "extra": "hello"})
        assert result == pytest.approx(6.0)

    def test_empty_values(self):
        """Empty values dict with variable references → None."""
        formula = _make_formula("x + y")
        result = formula.evaluate({})
        assert result is None

    def test_constant_expression(self):
        """Expression with no variables should work."""
        formula = _make_formula("2 + 3 * 4")
        result = formula.evaluate({})
        assert result == pytest.approx(14.0)

    def test_float_precision(self):
        formula = _make_formula("a / b")
        result = formula.evaluate({"a": 1, "b": 3})
        assert result == pytest.approx(0.333333, rel=1e-4)

    def test_large_numbers(self):
        formula = _make_formula("a * b")
        result = formula.evaluate({"a": 1_000_000, "b": 1_000_000})
        assert result == pytest.approx(1e12)


# ===========================================================================
# TestCalculatedFieldValidation — validate_definition() tests
# ===========================================================================

class TestCalculatedFieldValidation:
    """Tests for DbFormulaDef.validate_definition() — unsafe keyword detection."""

    def test_valid_formula(self):
        formula = _make_formula("a + b")
        errors = formula.validate_definition()
        assert errors == []

    def test_unsafe_keyword_import(self):
        formula = _make_formula("import os")
        errors = formula.validate_definition()
        assert any("import" in e for e in errors)

    def test_unsafe_keyword_exec(self):
        formula = _make_formula("exec('print(1)')")
        errors = formula.validate_definition()
        assert any("exec" in e for e in errors)

    def test_unsafe_keyword_eval(self):
        formula = _make_formula("eval('1+1')")
        errors = formula.validate_definition()
        assert any("eval" in e for e in errors)

    def test_unsafe_keyword_dunder(self):
        formula = _make_formula("__import__('os')")
        errors = formula.validate_definition()
        assert any("__" in e for e in errors)

    def test_unsafe_keyword_open(self):
        formula = _make_formula("open('/etc/passwd')")
        errors = formula.validate_definition()
        assert any("open" in e for e in errors)

    def test_empty_expression_error(self):
        formula = DbFormulaDef(name="empty", expression="")
        errors = formula.validate_definition()
        assert any("expression" in e for e in errors)

    def test_complex_safe_expression(self):
        """A complex but safe expression should produce no errors."""
        formula = _make_formula("((salesAmount - discountAmount) * 0.9) / totalCount")
        errors = formula.validate_definition()
        assert errors == []


# ===========================================================================
# TestFormulaOperator enum
# ===========================================================================

class TestFormulaOperator:
    def test_operator_values(self):
        assert FormulaOperator.ADD.value == "+"
        assert FormulaOperator.SUBTRACT.value == "-"
        assert FormulaOperator.MULTIPLY.value == "*"
        assert FormulaOperator.DIVIDE.value == "/"
        assert FormulaOperator.MODULO.value == "%"


# ===========================================================================
# v1.4 M4 Step 4.5 — A-tier real SQLite E2E:
#   sum / avg / count(distinct(if(...))) parity against native CASE WHEN
# ===========================================================================


def _pass_through(name: str) -> str:
    """Identity field resolver — tests reference physical columns directly."""
    return name


@pytest.fixture
def sqlite_conn():
    """In-memory SQLite with a small order-style fixture.

    Rows exercise every E2E case:
      - varied ``state`` for ``if(state == ...)`` and ``in(...)`` branches
      - some NULL ``parent_id`` for ``is_null(parent_id)``
      - ``amount`` spans zero, negatives, and >1000 to exercise filters
      - ``partner_id`` duplicates for ``count(distinct(...))``
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE orders ("
        "  id INTEGER PRIMARY KEY, state TEXT, amount REAL, "
        "  parent_id INTEGER, partner_id INTEGER"
        ")"
    )
    rows = [
        # (state,    amount,  parent_id, partner_id)
        ("posted",    100.0,  None,  10),
        ("posted",    250.0,     1,   10),  # same partner as row #1
        ("draft",     0.0,    None,  20),
        ("draft",     -30.0,  None,  20),
        ("cancel",   1500.0,     2,   30),
        ("posted",    800.0,     3,   40),
        ("posted",    5.0,     None,  50),
    ]
    cur.executemany(
        "INSERT INTO orders (state, amount, parent_id, partner_id) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def sqlite_compiler():
    return FormulaCompiler(SqlDialect.of("sqlite"))


def _execute(
    conn: sqlite3.Connection,
    select_sql: str,
    params: tuple,
) -> list[tuple]:
    """Run a single aggregate SELECT and return rows."""
    cur = conn.cursor()
    cur.execute(f"SELECT {select_sql} FROM orders", params)
    return cur.fetchall()


def _scalar(conn: sqlite3.Connection, select_sql: str, params: tuple):
    rows = _execute(conn, select_sql, params)
    assert len(rows) == 1 and len(rows[0]) == 1
    return rows[0][0]


class TestCalculatedFieldsE2ESqlite:
    """Real-SQLite parity tests for the ``sum/avg/count(distinct(if(...)))``
    aggregation-over-conditional pattern (Spec v1 §4).

    Each case compiles a formula through :class:`FormulaCompiler`, executes
    the result against the in-memory fixture, and compares to the CASE
    WHEN baseline hand-written in SQL.
    """

    # ---------- E2E-01: sum(if(==, col, 0)) -------------------------------

    def test_sum_if_equality(self, sqlite_conn, sqlite_compiler):
        compiled = sqlite_compiler.compile(
            "sum(if(state == 'posted', amount, 0))",
            _pass_through,
        )
        assert "IIF(" not in compiled.sql_fragment  # parity.md §7
        assert "CASE WHEN" in compiled.sql_fragment
        actual = _scalar(sqlite_conn, compiled.sql_fragment, compiled.bind_params)
        baseline = _scalar(
            sqlite_conn,
            "SUM(CASE WHEN state = ? THEN amount ELSE ? END)",
            ("posted", 0),
        )
        assert actual == baseline == pytest.approx(100 + 250 + 800 + 5)

    # ---------- E2E-02: avg(if(>, col, null)) -----------------------------

    def test_avg_if_with_null_else(self, sqlite_conn, sqlite_compiler):
        compiled = sqlite_compiler.compile(
            "avg(if(amount > 0, amount, null))",
            _pass_through,
        )
        assert "IIF(" not in compiled.sql_fragment
        assert "ELSE NULL" in compiled.sql_fragment
        actual = _scalar(sqlite_conn, compiled.sql_fragment, compiled.bind_params)
        baseline = _scalar(
            sqlite_conn,
            "AVG(CASE WHEN amount > ? THEN amount END)",
            (0,),
        )
        # Both drop the -30 negative and the 0 row from the mean.
        assert actual == baseline
        assert actual == pytest.approx((100 + 250 + 1500 + 800 + 5) / 5)

    # ---------- E2E-03: count(distinct(if(in(...), col, null))) ----------

    def test_count_distinct_if_in(self, sqlite_conn, sqlite_compiler):
        compiled = sqlite_compiler.compile(
            "count(distinct(if(state in ('draft', 'posted'), partner_id, null)))",
            _pass_through,
        )
        # parity.md §7: count(distinct(if(c, col, null))) drops ELSE NULL.
        assert "IIF(" not in compiled.sql_fragment
        assert "COUNT(DISTINCT" in compiled.sql_fragment
        assert "ELSE NULL" not in compiled.sql_fragment
        actual = _scalar(sqlite_conn, compiled.sql_fragment, compiled.bind_params)
        baseline = _scalar(
            sqlite_conn,
            "COUNT(DISTINCT CASE WHEN state IN (?, ?) THEN partner_id END)",
            ("draft", "posted"),
        )
        # draft → partner 20; posted → partners 10, 40, 50. Distinct = 4.
        assert actual == baseline == 4

    # ---------- E2E-04: sum(if(is_null(x), col, 0)) -----------------------

    def test_sum_if_is_null(self, sqlite_conn, sqlite_compiler):
        compiled = sqlite_compiler.compile(
            "sum(if(is_null(parent_id), amount, 0))",
            _pass_through,
        )
        assert "parent_id IS NULL" in compiled.sql_fragment
        actual = _scalar(sqlite_conn, compiled.sql_fragment, compiled.bind_params)
        baseline = _scalar(
            sqlite_conn,
            "SUM(CASE WHEN parent_id IS NULL THEN amount ELSE ? END)",
            (0,),
        )
        # NULL parent_id rows: 100, 0, -30, 5.
        assert actual == baseline == pytest.approx(100 + 0 + (-30) + 5)

    # ---------- E2E-05: avg(if(between(x, lo, hi), x, null)) --------------

    def test_avg_if_between(self, sqlite_conn, sqlite_compiler):
        compiled = sqlite_compiler.compile(
            "avg(if(between(amount, 100, 1000), amount, null))",
            _pass_through,
        )
        assert "IIF(" not in compiled.sql_fragment
        assert "BETWEEN" in compiled.sql_fragment
        actual = _scalar(sqlite_conn, compiled.sql_fragment, compiled.bind_params)
        baseline = _scalar(
            sqlite_conn,
            "AVG(CASE WHEN amount BETWEEN ? AND ? THEN amount END)",
            (100, 1000),
        )
        # Values in [100, 1000]: 100, 250, 800 → avg = (100+250+800)/3
        assert actual == baseline == pytest.approx((100 + 250 + 800) / 3)

    # ---------- bind-param ordering parity (Spec parity.md §2.4) ---------

    def test_bind_params_follow_left_to_right_dfs(self, sqlite_compiler):
        """R-1 says params follow a pre-order DFS left-to-right."""
        compiled = sqlite_compiler.compile(
            "if(state in ('a', 'b', 'c'), 1, 0)",
            _pass_through,
        )
        # Order: state (no param), 'a', 'b', 'c', 1, 0 → params = (a,b,c,1,0)
        assert compiled.bind_params == ("a", "b", "c", 1, 0)

    def test_compile_output_never_uses_iif(self, sqlite_compiler):
        """parity.md §7: FormulaCompiler emits CASE WHEN, never IIF()."""
        for expression in [
            "if(state == 'posted', 1, 0)",
            "sum(if(amount > 0, amount, 0))",
            "avg(if(between(amount, 100, 1000), amount, null))",
        ]:
            compiled = sqlite_compiler.compile(expression, _pass_through)
            assert "IIF(" not in compiled.sql_fragment.upper() \
                or "CASE WHEN" in compiled.sql_fragment
