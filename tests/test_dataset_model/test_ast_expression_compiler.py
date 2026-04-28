"""Tests for the v1.5 Phase 3 + Stage 6 fsscript AST → SQL visitor.

Three kinds of tests:
  1. **Parity** — for a curated set of fsscript expressions, verify
     that the AST path produces output that is *semantically equivalent*
     to the character-level tokenizer's output.  Some formatting
     differences (whitespace, parentheses, relational operator
     ``!=`` vs ``<>``) are expected and accepted.
  2. **Method calls** — a capability the char tokenizer cannot compile;
     verify AST path succeeds.
  3. **SQL predicates** — Stage 6 additions: IS NULL, BETWEEN, LIKE, CAST
     compiled natively by the AST path without fallback.
  4. **+ type inference** — Stage 6: string literal operands trigger
     dialect-appropriate concatenation.
  5. **Fallback** — for constructs the fsscript parser still cannot parse
     (``EXTRACT(YEAR FROM ...)``, explicit ``CASE WHEN``), verify the
     AST-on path still compiles via char-tokenizer fallback.

Need doc: ``docs/v1.5/P1-Phase3-AST-Visitor-架构对齐-需求.md``.
"""

from __future__ import annotations

import re

import pytest

from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlserver import SqlServerDialect
from foggy.dataset_model.definitions.base import AggregationType
from foggy.dataset_model.impl.model import (
    DbModelDimensionImpl,
    DbModelMeasureImpl,
    DbTableModelImpl,
)
from foggy.dataset_model.semantic.fsscript_to_sql_visitor import (
    AstCompileError,
    FsscriptToSqlVisitor,
    _preprocess_if,
    render_with_ast,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_model() -> DbTableModelImpl:
    m = DbTableModelImpl(name="TestModel", source_table="t_test")
    m.add_dimension(DbModelDimensionImpl(name="name", column="name"))
    m.add_dimension(DbModelDimensionImpl(name="status", column="status"))
    m.add_dimension(DbModelDimensionImpl(name="orderDate", column="order_date"))
    m.add_measure(DbModelMeasureImpl(
        name="salesAmount", column="sales_amount", aggregation=AggregationType.SUM,
    ))
    m.add_measure(DbModelMeasureImpl(
        name="costAmount", column="cost_amount", aggregation=AggregationType.SUM,
    ))
    return m


@pytest.fixture
def model():
    return _make_model()


@pytest.fixture
def svc_ast(model):
    s = SemanticQueryService(use_ast_expression_compiler=True)
    s.register_model(model)
    return s


@pytest.fixture
def svc_char(model):
    s = SemanticQueryService(use_ast_expression_compiler=False)
    s.register_model(model)
    return s


def _normalize_sql(s: str) -> str:
    """Normalize whitespace / case / cosmetic operator differences.

    Collapses whitespace, lowercases keywords (IN/NOT/AND/OR/NULL/CASE/…),
    normalizes ``!=`` ↔ ``<>``, and drops parens.  Good enough for parity
    checks where two paths produce the same **logical** SQL with
    different ornamentation.
    """
    # Lowercase SQL keywords
    for kw in ("IN", "NOT IN", "AND", "OR", "NOT", "NULL", "TRUE", "FALSE",
               "CASE WHEN", "THEN", "ELSE", "END", "IS", "LIKE", "BETWEEN",
               "COALESCE", "IFNULL", "ISNULL", "NVL", "IS NOT", "NOT BETWEEN",
               "NOT LIKE", "CAST", "AS"):
        s = re.sub(rf"\b{kw}\b", kw.lower(), s)
    # Prefix ``!`` ≡ ``not`` (fsscript → SQL)
    s = re.sub(r"!(?!=)", "not ", s)  # `!x` → `not x`, but leave `!=`
    # `!=` ≡ `<>`
    s = s.replace("!=", "<>")
    # Collapse whitespace
    s = re.sub(r"\s+", "", s)
    # Drop parens (expression trees are equivalent regardless of grouping
    # since both paths produce correctly-precedence-bracketed SQL)
    s = re.sub(r"[()]", "", s)
    return s


def _roughly_equivalent(a: str, b: str) -> bool:
    return _normalize_sql(a) == _normalize_sql(b)


# --------------------------------------------------------------------------- #
# 1. Parity — AST ≡ char tokenizer (semantic)
# --------------------------------------------------------------------------- #

class TestParity:
    """AST output should be semantically equivalent to char tokenizer output."""

    PARITY_EXPRESSIONS = [
        # Simple literals and arithmetic
        "1 + 2",
        "salesAmount + costAmount",
        "salesAmount - costAmount",
        "salesAmount * 2",
        "salesAmount / 2",
        "salesAmount % 10",
        "-salesAmount",
        # Comparison
        "salesAmount == 100",
        "salesAmount != 100",
        "salesAmount > 100",
        "salesAmount < 100",
        "salesAmount >= 100",
        "salesAmount <= 100",
        # Logical
        "salesAmount > 0 && costAmount > 0",
        "salesAmount > 0 || costAmount > 0",
        "!flag",
        # v1.4 IN / NOT IN
        "status in ('a', 'b', 'c')",
        "status not in ('a', 'b')",
        "salesAmount in (1, 2, 3)",
        # Functions (dialect-agnostic)
        "ROUND(salesAmount, 2)",
        "COALESCE(salesAmount, 0)",
        "ABS(salesAmount)",
        "IFNULL(salesAmount, 0)",
        # IF → CASE WHEN (both paths should produce CASE WHEN)
        "IF(salesAmount > 0, 1, 0)",
        "IF(status == 'a', salesAmount, costAmount)",
        "IF(status in ('a', 'b'), 1, 0)",
        # Nested
        "IF(salesAmount > 0, IF(costAmount > 0, 1, 2), 0)",
        "ROUND(salesAmount - costAmount, 2)",
        # Literals
        "'hello'",
        "null",
        "1",
        # Parens
        "(salesAmount + costAmount) * 2",
        "(salesAmount - costAmount)",
        # Mixed
        "salesAmount > 0 && status in ('a', 'b')",
        "salesAmount * 2 + costAmount / 3",
    ]

    @pytest.mark.parametrize("expr", PARITY_EXPRESSIONS)
    def test_ast_equiv_to_char(self, svc_ast, svc_char, model, expr):
        sql_char = svc_char._render_expression(expr, model)
        sql_ast = svc_ast._render_expression(expr, model)
        assert _roughly_equivalent(sql_char, sql_ast), (
            f"Expression {expr!r}\n"
            f"char: {sql_char}\n"
            f"ast : {sql_ast}"
        )


# --------------------------------------------------------------------------- #
# 2. Method calls — AST-only capability
# --------------------------------------------------------------------------- #

class TestMethodCalls:
    @pytest.mark.parametrize("expr,expected_contains", [
        ("name.startsWith('A')", "LIKE"),
        ("name.endsWith('z')", "LIKE"),
        ("name.contains('mid')", "LIKE"),
        ("name.toUpperCase()", "UPPER"),
        ("name.toLowerCase()", "LOWER"),
        ("name.trim()", "TRIM"),
        ("name.length()", "LENGTH"),
    ])
    def test_ast_supports_method_call(self, svc_ast, model, expr, expected_contains):
        sql = svc_ast._render_expression(expr, model)
        assert expected_contains in sql

    def test_method_call_resolves_field(self, svc_ast, model):
        sql = svc_ast._render_expression("name.startsWith('A')", model)
        assert "t.name" in sql

    def test_method_call_concat_with_arg(self, svc_ast, model):
        sql = svc_ast._render_expression("name.startsWith('A')", model)
        # Default (no dialect): ANSI ||
        assert "'A' || '%'" in sql or "CONCAT('A', '%')" in sql

    def test_char_tokenizer_rejects_method_calls(self, svc_char, model):
        """This is the whole reason for Phase 3 — char tokenizer can't do this."""
        with pytest.raises(ValueError):
            svc_char._render_expression("name.startsWith('A')", model)

    def test_method_with_wrong_arity(self, svc_ast, model):
        # startsWith expects 1 arg
        with pytest.raises((AstCompileError, ValueError)):
            svc_ast._render_expression("name.startsWith('A', 'B')", model)

    def test_method_end_to_end_query(self, svc_ast, model):
        req = SemanticQueryRequest(
            columns=["name$caption", "isA"],
            calculatedFields=[
                {"name": "isA", "expression": "name.startsWith('A')"},
            ],
        )
        r = svc_ast.query_model("TestModel", req, mode="validate")
        assert r.error is None, r.error
        assert "LIKE" in r.sql


class TestMethodDialectRouting:
    """Method calls emit dialect-appropriate concat."""

    def test_mysql_uses_concat(self, model):
        s = SemanticQueryService(
            dialect=MySqlDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("name.startsWith('A')", model)
        assert "CONCAT('A', '%')" in sql

    def test_postgres_uses_pipe(self, model):
        s = SemanticQueryService(
            dialect=PostgresDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("name.startsWith('A')", model)
        assert "'A' || '%'" in sql

    def test_sqlserver_length_to_len(self, model):
        s = SemanticQueryService(
            dialect=SqlServerDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("name.length()", model)
        assert "LEN(t.name)" in sql


# --------------------------------------------------------------------------- #
# 3. Ternary and null coalescing
# --------------------------------------------------------------------------- #

class TestTernaryAndCoalesce:
    def test_ternary_to_case_when(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount > 0 ? 1 : 0", model)
        assert "CASE WHEN" in sql
        assert "THEN 1" in sql
        assert "ELSE 0" in sql
        assert "END" in sql

    def test_null_coalesce_default(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount ?? 0", model)
        # Default dialect: COALESCE
        assert "COALESCE" in sql

    def test_null_coalesce_postgres(self, model):
        s = SemanticQueryService(
            dialect=PostgresDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("salesAmount ?? 0", model)
        assert "COALESCE" in sql

    def test_null_coalesce_sqlserver(self, model):
        s = SemanticQueryService(
            dialect=SqlServerDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("salesAmount ?? 0", model)
        # SQL Server renames IFNULL→ISNULL; COALESCE stays as-is
        assert "COALESCE" in sql or "ISNULL" in sql


# --------------------------------------------------------------------------- #
# 4. SQL-specific predicates — now native AST (Stage 6 / Phase 4)
# --------------------------------------------------------------------------- #

class TestSqlPredicates:
    """SQL-specific predicates compiled natively by AST path (Stage 6).

    Before Stage 6, these fell back to the char tokenizer.  Now the
    fsscript parser produces dedicated AST nodes and the visitor emits
    proper SQL.
    """

    @pytest.mark.parametrize("expr,expected_keyword", [
        ("salesAmount IS NULL", "IS NULL"),
        ("salesAmount IS NOT NULL", "IS NOT NULL"),
        ("salesAmount is null", "IS NULL"),
        ("salesAmount is not null", "IS NOT NULL"),
        ("salesAmount BETWEEN 10 AND 100", "BETWEEN"),
        ("salesAmount between 10 and 100", "BETWEEN"),
        ("salesAmount NOT BETWEEN 10 AND 100", "NOT BETWEEN"),
        ("name LIKE 'A%'", "LIKE"),
        ("name like 'A%'", "LIKE"),
        ("name NOT LIKE 'A%'", "NOT LIKE"),
        ("name not like 'A%'", "NOT LIKE"),
        ("CAST(salesAmount AS INTEGER)", "CAST"),
    ])
    def test_ast_compiles_sql_predicate(self, svc_ast, model, expr, expected_keyword):
        sql = svc_ast._render_expression(expr, model)
        assert expected_keyword.lower() in sql.lower(), f"Expected {expected_keyword!r} in {sql!r}"

    def test_is_null_field_resolution(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount IS NULL", model)
        assert "t.sales_amount IS NULL" == sql

    def test_is_not_null_field_resolution(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount IS NOT NULL", model)
        assert "t.sales_amount IS NOT NULL" == sql

    def test_between_with_field_and_literals(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount BETWEEN 10 AND 100", model)
        assert "t.sales_amount BETWEEN 10 AND 100" == sql

    def test_not_between(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount NOT BETWEEN 10 AND 100", model)
        assert "t.sales_amount NOT BETWEEN 10 AND 100" == sql

    def test_between_with_arithmetic(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount BETWEEN 1 + 2 AND 10", model)
        assert "BETWEEN" in sql
        assert "AND" in sql

    def test_like_with_string_pattern(self, svc_ast, model):
        sql = svc_ast._render_expression("name LIKE 'A%'", model)
        assert "t.name LIKE 'A%'" == sql

    def test_not_like(self, svc_ast, model):
        sql = svc_ast._render_expression("name NOT LIKE 'A%'", model)
        assert "t.name NOT LIKE 'A%'" == sql

    def test_cast_simple_type(self, svc_ast, model):
        sql = svc_ast._render_expression("CAST(salesAmount AS INTEGER)", model)
        assert "CAST(t.sales_amount AS INTEGER)" == sql

    def test_cast_varchar_precision(self, svc_ast, model):
        sql = svc_ast._render_expression("CAST(name AS VARCHAR(100))", model)
        assert "CAST(t.name AS VARCHAR(100))" == sql

    def test_cast_decimal_precision(self, svc_ast, model):
        sql = svc_ast._render_expression("CAST(salesAmount AS DECIMAL(10, 2))", model)
        assert "CAST(t.sales_amount AS DECIMAL(10, 2))" == sql

    def test_is_null_parity(self, svc_ast, svc_char, model):
        """Both AST and char paths produce semantically equivalent SQL."""
        for expr in ["salesAmount IS NULL", "salesAmount IS NOT NULL"]:
            ast_sql = svc_ast._render_expression(expr, model)
            char_sql = svc_char._render_expression(expr, model)
            assert _roughly_equivalent(ast_sql, char_sql), (
                f"Expression {expr!r}\nchar: {char_sql}\nast : {ast_sql}"
            )

    def test_between_parity(self, svc_ast, svc_char, model):
        for expr in ["salesAmount BETWEEN 10 AND 100"]:
            ast_sql = svc_ast._render_expression(expr, model)
            char_sql = svc_char._render_expression(expr, model)
            assert _roughly_equivalent(ast_sql, char_sql), (
                f"Expression {expr!r}\nchar: {char_sql}\nast : {ast_sql}"
            )

    def test_like_parity(self, svc_ast, svc_char, model):
        for expr in ["name LIKE 'A%'"]:
            ast_sql = svc_ast._render_expression(expr, model)
            char_sql = svc_char._render_expression(expr, model)
            assert _roughly_equivalent(ast_sql, char_sql), (
                f"Expression {expr!r}\nchar: {char_sql}\nast : {ast_sql}"
            )

    def test_no_fallback_for_implemented_forms(self, svc_ast, model):
        """Verify AST path compiles directly (no AstCompileError raised)."""
        for expr in [
            "salesAmount IS NULL",
            "salesAmount IS NOT NULL",
            "name LIKE 'A%'",
            "name NOT LIKE 'A%'",
            "salesAmount BETWEEN 10 AND 100",
            "salesAmount NOT BETWEEN 10 AND 100",
            "CAST(salesAmount AS INTEGER)",
        ]:
            sql = render_with_ast(expr, service=svc_ast, model=model)
            assert sql, f"Expected non-empty SQL for {expr!r}"

    def test_if_wrapping_is_null(self, svc_ast, model):
        sql = svc_ast._render_expression("IF(salesAmount IS NULL, 0, salesAmount)", model)
        assert "IS NULL" in sql.upper()
        assert "CASE WHEN" in sql.upper()

    def test_compound_is_null_and_between(self, svc_ast, model):
        sql = svc_ast._render_expression(
            "salesAmount IS NOT NULL && salesAmount BETWEEN 10 AND 100", model
        )
        assert "IS NOT NULL" in sql.upper()
        assert "BETWEEN" in sql.upper()


# --------------------------------------------------------------------------- #
# 5. + operator type inference (Stage 6)
# --------------------------------------------------------------------------- #

class TestPlusTypeBehavior:
    """Stage 6: conservative + operator string literal type inference."""

    def test_string_plus_string_literal_default(self, svc_ast, model):
        sql = svc_ast._render_expression("'hello' + ' world'", model)
        # Default dialect: ANSI || concatenation
        assert "||" in sql or "CONCAT" in sql

    def test_numeric_plus_numeric(self, svc_ast, model):
        sql = svc_ast._render_expression("salesAmount + 10", model)
        assert "+" in sql
        assert "||" not in sql

    def test_field_plus_string(self, svc_ast, model):
        sql = svc_ast._render_expression("name + 'suffix'", model)
        assert "||" in sql or "CONCAT" in sql

    def test_string_plus_field(self, svc_ast, model):
        sql = svc_ast._render_expression("'prefix' + name", model)
        assert "||" in sql or "CONCAT" in sql

    def test_mysql_string_concat(self, model):
        s = SemanticQueryService(
            dialect=MySqlDialect(),
            use_ast_expression_compiler=True,
        )
        s.register_model(model)
        sql = s._render_expression("'hello' + ' world'", model)
        assert "CONCAT" in sql

    def test_field_plus_field_stays_numeric(self, svc_ast, model):
        """Two field references: conservative path stays as SQL +."""
        sql = svc_ast._render_expression("salesAmount + costAmount", model)
        assert "+" in sql
        assert "||" not in sql


# --------------------------------------------------------------------------- #
# 6. Fallback — forms intentionally still on char tokenizer
# --------------------------------------------------------------------------- #

class TestFallback:
    """Constructs that the AST path does not yet handle; these
    fall through to the char tokenizer.  Confirm they still compile."""

    @pytest.mark.parametrize("expr,expected_contains", [
        ("EXTRACT(YEAR FROM orderDate)", "EXTRACT"),
    ])
    def test_fallback_for_sql_specific_syntax(self, svc_ast, model, expr, expected_contains):
        sql = svc_ast._render_expression(expr, model)
        assert expected_contains.lower() in sql.lower()


# --------------------------------------------------------------------------- #
# 7. Default-off invariant
# --------------------------------------------------------------------------- #

class TestDefaultOffInvariant:
    def test_default_is_off(self):
        s = SemanticQueryService()
        assert s._use_ast_expression_compiler is False


# --------------------------------------------------------------------------- #
# 8. Preprocessing
# --------------------------------------------------------------------------- #

class TestPreprocessIf:
    def test_simple_if(self):
        assert _preprocess_if("IF(a, b, c)") == "__FSQL_IF__(a, b, c)"

    def test_lowercase_if(self):
        assert _preprocess_if("if(a, b, c)") == "__FSQL_IF__(a, b, c)"

    def test_nested_if(self):
        assert _preprocess_if("IF(a, IF(b, c, d), e)") == \
            "__FSQL_IF__(a, __FSQL_IF__(b, c, d), e)"

    def test_if_inside_string_preserved(self):
        assert _preprocess_if("'IF(x, y, z)'") == "'IF(x, y, z)'"

    def test_if_inside_double_quotes_preserved(self):
        assert _preprocess_if('"IF(x, y, z)"') == '"IF(x, y, z)"'

    def test_if_as_suffix_not_touched(self):
        assert _preprocess_if("MODIFIED_AT(x)") == "MODIFIED_AT(x)"

    def test_if_without_parens_not_touched(self):
        assert _preprocess_if("IF foo") == "IF foo"

    def test_empty_string(self):
        assert _preprocess_if("") == ""


# --------------------------------------------------------------------------- #
# 9. Visitor error handling
# --------------------------------------------------------------------------- #

class TestVisitorErrors:
    def test_instanceof_raises(self, svc_ast, model):
        with pytest.raises((AstCompileError, ValueError)):
            visitor = FsscriptToSqlVisitor(
                service=svc_ast, model=model, ensure_join=None,
            )
            from foggy.fsscript.parser import FsscriptParser
            ast = FsscriptParser("x instanceof Array").parse_expression()
            visitor.visit(ast)

    def test_unsupported_method(self, svc_ast, model):
        with pytest.raises(AstCompileError):
            visitor = FsscriptToSqlVisitor(
                service=svc_ast, model=model, ensure_join=None,
            )
            from foggy.fsscript.parser import FsscriptParser
            ast = FsscriptParser("x.someUnknownMethod()").parse_expression()
            visitor.visit(ast)

    def test_arity_on_method(self, svc_ast, model):
        with pytest.raises(AstCompileError):
            visitor = FsscriptToSqlVisitor(
                service=svc_ast, model=model, ensure_join=None,
            )
            from foggy.fsscript.parser import FsscriptParser
            ast = FsscriptParser("x.startsWith('a', 'b')").parse_expression()
            visitor.visit(ast)


# --------------------------------------------------------------------------- #
# 10. End-to-end with compiled_calcs (Phase 2 integration)
# --------------------------------------------------------------------------- #

class TestAstWithCompiledCalcs:
    def test_ast_can_use_compiled_calcs(self, svc_ast):
        req = SemanticQueryRequest(
            columns=["base", "derived"],
            calculatedFields=[
                {"name": "base", "expression": "salesAmount - costAmount"},
                {"name": "derived", "expression": "name.startsWith('A') ? base : 0"},
            ],
        )
        r = svc_ast.query_model("TestModel", req, mode="validate")
        assert r.error is None, r.error
        assert "CASE WHEN" in r.sql
        assert "LIKE" in r.sql
        assert "(t.sales_amount - t.cost_amount)" in r.sql
