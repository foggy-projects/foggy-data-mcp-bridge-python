"""Cross-dialect function translation for computed-field SQL emission.

Tests ``FDialect.build_function_call`` / ``translate_function`` and the
end-to-end integration through ``SemanticQueryService._render_expression``.

契约对齐 Java ``DialectFunctionTranslationTest.java``:
  ``foggy-data-mcp-bridge/foggy-dataset-model/src/test/java/
    com/foggyframework/dataset/db/model/dialect/DialectFunctionTranslationTest.java``

Python 侧需求：``docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md``.
"""

from __future__ import annotations

import pytest

from foggy.dataset.dialects.base import FDialect
from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset.dialects.sqlserver import SqlServerDialect
from foggy.dataset_model.impl.model import DbModelDimensionImpl, DbModelMeasureImpl, DbTableModelImpl
from foggy.dataset_model.definitions.base import AggregationType
from foggy.dataset_model.semantic.service import SemanticQueryService


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _make_test_model() -> DbTableModelImpl:
    """Lightweight model used across dialect tests."""
    model = DbTableModelImpl(name="TestModel", source_table="t_test")
    model.add_dimension(DbModelDimensionImpl(name="status", column="status"))
    model.add_dimension(DbModelDimensionImpl(name="name", column="name"))
    model.add_dimension(DbModelDimensionImpl(name="orderDate", column="order_date"))
    model.add_measure(DbModelMeasureImpl(
        name="salesAmount", column="sales_amount", aggregation=AggregationType.SUM,
    ))
    return model


def _svc(dialect: FDialect | None) -> SemanticQueryService:
    svc = SemanticQueryService(dialect=dialect)
    svc.register_model(_make_test_model())
    return svc


# --------------------------------------------------------------------------- #
# 1. build_function_call — direct API contract
# --------------------------------------------------------------------------- #

class TestPostgresBuildFunctionCall:
    """PostgresDialect complex translations."""

    def setup_method(self):
        self.d = PostgresDialect()

    def test_year_to_extract(self):
        assert self.d.build_function_call("YEAR", ["t.d"]) == "EXTRACT(YEAR FROM t.d)"

    def test_month_to_extract(self):
        assert self.d.build_function_call("MONTH", ["t.d"]) == "EXTRACT(MONTH FROM t.d)"

    def test_day_to_extract(self):
        assert self.d.build_function_call("DAY", ["t.d"]) == "EXTRACT(DAY FROM t.d)"

    def test_hour_to_extract(self):
        assert self.d.build_function_call("HOUR", ["t.d"]) == "EXTRACT(HOUR FROM t.d)"

    def test_minute_to_extract(self):
        assert self.d.build_function_call("MINUTE", ["t.d"]) == "EXTRACT(MINUTE FROM t.d)"

    def test_second_to_extract(self):
        assert self.d.build_function_call("SECOND", ["t.d"]) == "EXTRACT(SECOND FROM t.d)"

    def test_date_format_to_to_char(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y-%m-%d'"])
        assert got == "TO_CHAR(t.d, 'YYYY-MM-DD')"

    def test_date_format_year_month(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y-%m'"])
        assert got == "TO_CHAR(t.d, 'YYYY-MM')"

    def test_date_format_full_month_name(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y-%M-%d'"])
        assert got == "TO_CHAR(t.d, 'YYYY-Month-DD')"

    def test_unknown_function_returns_none(self):
        assert self.d.build_function_call("COALESCE", ["a", "b"]) is None

    def test_wrong_arity_returns_none(self):
        # YEAR expects 1 arg; 2 args → can't translate, return None (fall through)
        assert self.d.build_function_call("YEAR", ["t.d", "extra"]) is None

    def test_none_inputs(self):
        assert self.d.build_function_call(None, ["a"]) is None
        assert self.d.build_function_call("YEAR", None) is None

    def test_case_insensitive(self):
        assert self.d.build_function_call("year", ["t.d"]) == "EXTRACT(YEAR FROM t.d)"


class TestSqliteBuildFunctionCall:
    """SqliteDialect uses strftime() with reversed args."""

    def setup_method(self):
        self.d = SqliteDialect()

    def test_year_to_strftime(self):
        got = self.d.build_function_call("YEAR", ["t.d"])
        assert got == "CAST(strftime('%Y', t.d) AS INTEGER)"

    def test_month_to_strftime(self):
        got = self.d.build_function_call("MONTH", ["t.d"])
        assert got == "CAST(strftime('%m', t.d) AS INTEGER)"

    def test_hour_to_strftime(self):
        got = self.d.build_function_call("HOUR", ["t.d"])
        assert got == "CAST(strftime('%H', t.d) AS INTEGER)"

    def test_minute_to_strftime(self):
        got = self.d.build_function_call("MINUTE", ["t.d"])
        assert got == "CAST(strftime('%M', t.d) AS INTEGER)"

    def test_second_to_strftime(self):
        got = self.d.build_function_call("SECOND", ["t.d"])
        assert got == "CAST(strftime('%S', t.d) AS INTEGER)"

    def test_date_format_args_reversed(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y-%m-%d'"])
        # SQLite uses MySQL-like format natively, just reverses arg order
        assert got == "strftime('%Y-%m-%d', t.d)"

    def test_none_inputs(self):
        assert self.d.build_function_call(None, ["a"]) is None
        assert self.d.build_function_call("YEAR", None) is None


class TestSqlServerBuildFunctionCall:
    """SqlServerDialect uses DATEPART and FORMAT."""

    def setup_method(self):
        self.d = SqlServerDialect()

    def test_hour_to_datepart(self):
        got = self.d.build_function_call("HOUR", ["t.d"])
        assert got == "DATEPART(HOUR, t.d)"

    def test_minute_to_datepart(self):
        got = self.d.build_function_call("MINUTE", ["t.d"])
        assert got == "DATEPART(MINUTE, t.d)"

    def test_second_to_datepart(self):
        got = self.d.build_function_call("SECOND", ["t.d"])
        assert got == "DATEPART(SECOND, t.d)"

    def test_year_is_native(self):
        """YEAR/MONTH/DAY are native SQL Server — build_function_call falls through."""
        assert self.d.build_function_call("YEAR", ["t.d"]) is None
        assert self.d.build_function_call("MONTH", ["t.d"]) is None
        assert self.d.build_function_call("DAY", ["t.d"]) is None

    def test_date_format_to_format(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y-%m-%d'"])
        assert got == "FORMAT(t.d, 'yyyy-MM-dd')"

    def test_date_format_mysql_time_fmt(self):
        got = self.d.build_function_call("DATE_FORMAT", ["t.d", "'%H:%i:%s'"])
        assert got == "FORMAT(t.d, 'HH:mm:ss')"


class TestMysqlBuildFunctionCall:
    """MySQL has no complex translations — build_function_call always returns None."""

    def setup_method(self):
        self.d = MySqlDialect()

    def test_year_passes_through(self):
        assert self.d.build_function_call("YEAR", ["t.d"]) is None

    def test_date_format_passes_through(self):
        assert self.d.build_function_call("DATE_FORMAT", ["t.d", "'%Y'"]) is None


# --------------------------------------------------------------------------- #
# 2. translate_function — simple rename via _get_function_mappings
# --------------------------------------------------------------------------- #

class TestTranslateFunctionRename:
    """Simple rename table for cross-dialect function aliases.

    对齐 Java ``DialectFunctionTranslationTest``:
    - IFNULL / NVL / ISNULL → dialect-native NULL coalescing
    - LEN ↔ LENGTH, SUBSTR ↔ SUBSTRING
    - POW → POWER (on PG / SQL Server), native on MySQL
    - CEIL → CEILING (on SQL Server)
    - STDDEV_POP/SAMP → STDEVP/STDEV (on SQL Server)
    """

    @pytest.mark.parametrize("dialect_cls,func,args,expected", [
        # NULL coalescing
        (MySqlDialect, "IFNULL", ["a", "0"], "IFNULL(a, 0)"),
        (MySqlDialect, "NVL", ["a", "0"], "IFNULL(a, 0)"),
        (MySqlDialect, "ISNULL", ["a", "0"], "IFNULL(a, 0)"),
        (PostgresDialect, "IFNULL", ["a", "0"], "COALESCE(a, 0)"),
        (PostgresDialect, "NVL", ["a", "0"], "COALESCE(a, 0)"),
        (PostgresDialect, "ISNULL", ["a", "0"], "COALESCE(a, 0)"),
        (SqliteDialect, "IFNULL", ["a", "0"], "IFNULL(a, 0)"),
        (SqliteDialect, "NVL", ["a", "0"], "IFNULL(a, 0)"),
        (SqlServerDialect, "IFNULL", ["a", "0"], "ISNULL(a, 0)"),
        (SqlServerDialect, "NVL", ["a", "0"], "ISNULL(a, 0)"),
        (SqlServerDialect, "COALESCE", ["a", "0"], "COALESCE(a, 0)"),
        # String length
        (SqlServerDialect, "LENGTH", ["a"], "LEN(a)"),
        (SqlServerDialect, "CHAR_LENGTH", ["a"], "LEN(a)"),
        (PostgresDialect, "LEN", ["a"], "LENGTH(a)"),
        # Substring
        (SqlServerDialect, "SUBSTR", ["a", "1", "3"], "SUBSTRING(a, 1, 3)"),
        (MySqlDialect, "SUBSTR", ["a", "1", "3"], "SUBSTRING(a, 1, 3)"),
        # Math
        (PostgresDialect, "POW", ["a", "2"], "POWER(a, 2)"),
        (SqlServerDialect, "POW", ["a", "2"], "POWER(a, 2)"),
        (MySqlDialect, "POW", ["a", "2"], "POW(a, 2)"),  # MySQL keeps POW native
        (SqlServerDialect, "CEIL", ["a"], "CEILING(a)"),
        # Postgres TRUNC ↔ MySQL TRUNCATE
        (MySqlDialect, "TRUNC", ["a", "2"], "TRUNCATE(a, 2)"),
        (PostgresDialect, "TRUNCATE", ["a", "2"], "TRUNC(a, 2)"),
        # Statistical (SQL Server only)
        (SqlServerDialect, "STDDEV_POP", ["a"], "STDEVP(a)"),
        (SqlServerDialect, "STDDEV_SAMP", ["a"], "STDEV(a)"),
        (SqlServerDialect, "VAR_POP", ["a"], "VARP(a)"),
        (SqlServerDialect, "VAR_SAMP", ["a"], "VAR(a)"),
    ])
    def test_rename(self, dialect_cls, func, args, expected):
        d = dialect_cls()
        assert d.translate_function(func, args) == expected

    def test_case_insensitive(self):
        d = PostgresDialect()
        assert d.translate_function("ifnull", ["a", "0"]) == "COALESCE(a, 0)"
        assert d.translate_function("IfNull", ["a", "0"]) == "COALESCE(a, 0)"

    def test_unknown_function_falls_through(self):
        d = PostgresDialect()
        assert d.translate_function("MY_CUSTOM_FN", ["a"]) == "MY_CUSTOM_FN(a)"

    def test_null_func_name(self):
        d = PostgresDialect()
        assert d.translate_function(None, []) is None


# --------------------------------------------------------------------------- #
# 3. DATE_FORMAT format-string translation table
# --------------------------------------------------------------------------- #

class TestPostgresDateFormatTranslation:
    """MySQL → Postgres format string via _translate_mysql_date_format."""

    @pytest.mark.parametrize("mysql_fmt,pg_fmt", [
        ("'%Y-%m-%d'", "'YYYY-MM-DD'"),
        ("'%Y-%m'", "'YYYY-MM'"),
        ("'%d/%m/%Y'", "'DD/MM/YYYY'"),
        ("'%H:%i:%s'", "'HH24:MI:SS'"),
        ("'%Y-%m-%d %H:%i:%s'", "'YYYY-MM-DD HH24:MI:SS'"),
        ("'%M %d, %Y'", "'Month DD, YYYY'"),
        ("'%a %b'", "'Dy Mon'"),
        ("'%W'", "'Day'"),
        ("'%j'", "'DDD'"),
        # unknown placeholder — left verbatim
        ("'%Z'", "'%Z'"),
    ])
    def test_translate(self, mysql_fmt, pg_fmt):
        assert PostgresDialect._translate_mysql_date_format(mysql_fmt) == pg_fmt

    def test_non_quoted_passed_through(self):
        # Arg wasn't a string literal (e.g. variable ref); still translate placeholders
        got = PostgresDialect._translate_mysql_date_format("%Y-%m")
        assert got == "YYYY-MM"


class TestSqlServerDateFormatTranslation:
    """MySQL → SQL Server format string."""

    @pytest.mark.parametrize("mysql_fmt,ss_fmt", [
        ("'%Y-%m-%d'", "'yyyy-MM-dd'"),
        ("'%Y-%m'", "'yyyy-MM'"),
        ("'%d/%m/%Y'", "'dd/MM/yyyy'"),
        ("'%H:%i:%s'", "'HH:mm:ss'"),
        ("'%Y-%m-%d %H:%i:%s'", "'yyyy-MM-dd HH:mm:ss'"),
    ])
    def test_translate(self, mysql_fmt, ss_fmt):
        assert SqlServerDialect._translate_mysql_date_format(mysql_fmt) == ss_fmt


# --------------------------------------------------------------------------- #
# 4. End-to-end: SemanticQueryService._resolve_expression_fields
# --------------------------------------------------------------------------- #

class TestEndToEndDialectSql:
    """Full path: dialect-aware SQL emission from a computed-field expression."""

    def test_postgres_date_format_and_year(self):
        svc = _svc(PostgresDialect())
        model = svc._models["TestModel"]
        assert (
            svc._resolve_expression_fields("DATE_FORMAT(orderDate, '%Y-%m')", model)
            == "TO_CHAR(t.order_date, 'YYYY-MM')"
        )
        assert (
            svc._resolve_expression_fields("YEAR(orderDate)", model)
            == "EXTRACT(YEAR FROM t.order_date)"
        )

    def test_sqlite_date_format_reversed(self):
        svc = _svc(SqliteDialect())
        model = svc._models["TestModel"]
        got = svc._resolve_expression_fields("DATE_FORMAT(orderDate, '%Y-%m-%d')", model)
        assert got == "strftime('%Y-%m-%d', t.order_date)"

    def test_sqlserver_hour_and_format(self):
        svc = _svc(SqlServerDialect())
        model = svc._models["TestModel"]
        assert (
            svc._resolve_expression_fields("HOUR(orderDate)", model)
            == "DATEPART(HOUR, t.order_date)"
        )
        assert (
            svc._resolve_expression_fields("DATE_FORMAT(orderDate, '%Y-%m')", model)
            == "FORMAT(t.order_date, 'yyyy-MM')"
        )

    def test_postgres_ifnull_to_coalesce(self):
        svc = _svc(PostgresDialect())
        model = svc._models["TestModel"]
        got = svc._resolve_expression_fields("IFNULL(salesAmount, 0)", model)
        assert got == "COALESCE(t.sales_amount, 0)"

    def test_sqlserver_length_to_len(self):
        svc = _svc(SqlServerDialect())
        model = svc._models["TestModel"]
        got = svc._resolve_expression_fields("CHAR_LENGTH(name)", model)
        assert got == "LEN(t.name)"

    def test_no_dialect_preserves_legacy_behavior(self):
        """dialect=None path must match pre-v1.5 output byte-for-byte."""
        svc = _svc(None)
        model = svc._models["TestModel"]
        # Date/function expressions pass through unchanged.
        assert (
            svc._resolve_expression_fields("DATE_FORMAT(orderDate, '%Y-%m')", model)
            == "DATE_FORMAT(t.order_date, '%Y-%m')"
        )
        assert (
            svc._resolve_expression_fields("YEAR(orderDate)", model)
            == "YEAR(t.order_date)"
        )
        assert (
            svc._resolve_expression_fields("IFNULL(salesAmount, 0)", model)
            == "IFNULL(t.sales_amount, 0)"
        )

    def test_mysql_dialect_minimal_impact(self):
        """MySQL dialect should NOT rewrite native functions."""
        svc = _svc(MySqlDialect())
        model = svc._models["TestModel"]
        assert (
            svc._resolve_expression_fields("DATE_FORMAT(orderDate, '%Y-%m')", model)
            == "DATE_FORMAT(t.order_date, '%Y-%m')"
        )
        assert (
            svc._resolve_expression_fields("YEAR(orderDate)", model)
            == "YEAR(t.order_date)"
        )

    def test_keyword_delimited_functions_bypass_dialect(self):
        """CAST / CONVERT / EXTRACT must not be routed through dialect."""
        svc = _svc(PostgresDialect())
        model = svc._models["TestModel"]
        assert (
            svc._resolve_expression_fields("CAST(salesAmount AS INTEGER)", model)
            == "CAST(t.sales_amount AS INTEGER)"
        )
        assert (
            svc._resolve_expression_fields("EXTRACT(YEAR FROM orderDate)", model)
            == "EXTRACT(YEAR FROM t.order_date)"
        )

    def test_in_operator_still_works_across_dialects(self):
        """Regression: v1.4 `in (...)` / `not in (...)` must keep working."""
        for dialect in [None, MySqlDialect(), PostgresDialect(), SqliteDialect(), SqlServerDialect()]:
            svc = _svc(dialect)
            model = svc._models["TestModel"]
            got = svc._resolve_expression_fields("status in ('a', 'b', 'c')", model)
            assert " IN" in got.upper() or " in" in got
            assert "'a'" in got and "'b'" in got and "'c'" in got

    def test_nested_if_coalesce_with_dialect(self):
        """Nested IF + COALESCE + date function — all translated in the right places."""
        svc = _svc(PostgresDialect())
        model = svc._models["TestModel"]
        expr = "IFNULL(if(status == 'a', YEAR(orderDate), 0), -1)"
        got = svc._resolve_expression_fields(expr, model)
        # Should: IFNULL → COALESCE, IF → CASE WHEN, YEAR → EXTRACT
        assert "COALESCE(" in got
        assert "CASE WHEN" in got
        assert "EXTRACT(YEAR FROM" in got
