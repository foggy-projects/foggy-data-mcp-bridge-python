"""Function arity validation for computed-field SQL compilation.

对齐 Java 侧在 grammar 层做的参数数量校验。
Python 侧在 ``SemanticQueryService._render_expression`` 的函数调用分支里
查表 ``_FUNCTION_ARITY``，不匹配时抛 ``ValueError``。

Python 侧需求：``docs/v1.5/P1-Phase1-Dialect函数翻译与arity校验-需求.md``.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.impl.model import DbModelDimensionImpl, DbModelMeasureImpl, DbTableModelImpl
from foggy.dataset_model.definitions.base import AggregationType
from foggy.dataset_model.semantic.service import SemanticQueryService


def _make_test_model() -> DbTableModelImpl:
    model = DbTableModelImpl(name="TestModel", source_table="t_test")
    model.add_dimension(DbModelDimensionImpl(name="name", column="name"))
    model.add_dimension(DbModelDimensionImpl(name="status", column="status"))
    model.add_dimension(DbModelDimensionImpl(name="orderDate", column="order_date"))
    model.add_measure(DbModelMeasureImpl(
        name="salesAmount", column="sales_amount", aggregation=AggregationType.SUM,
    ))
    return model


@pytest.fixture
def svc():
    svc = SemanticQueryService()
    svc.register_model(_make_test_model())
    return svc


@pytest.fixture
def model():
    return _make_test_model()


# --------------------------------------------------------------------------- #
# 1. Positive cases — correct arity, should NOT raise
# --------------------------------------------------------------------------- #

class TestArityPositive:
    @pytest.mark.parametrize("expr", [
        # Fixed 1-arg
        "ABS(salesAmount)",
        "FLOOR(salesAmount)",
        "CEIL(salesAmount)",
        "SQRT(salesAmount)",
        "UPPER(name)",
        "LOWER(name)",
        "LTRIM(name)",
        "RTRIM(name)",
        "TRIM(name)",
        "CHAR_LENGTH(name)",
        "YEAR(orderDate)",
        "MONTH(orderDate)",
        "DAY(orderDate)",
        # Fixed 2-arg
        "IFNULL(salesAmount, 0)",
        "NVL(salesAmount, 0)",
        "NULLIF(salesAmount, 0)",
        "MOD(salesAmount, 10)",
        "POWER(salesAmount, 2)",
        "POW(salesAmount, 2)",
        "LEFT(name, 3)",
        "RIGHT(name, 3)",
        "DATE_FORMAT(orderDate, '%Y-%m')",
        "DATEDIFF(orderDate, orderDate)",
        # Fixed 3-arg
        "IF(status == 'a', 1, 0)",
        "REPLACE(name, 'a', 'b')",
        "LPAD(name, 10, ' ')",
        "RPAD(name, 10, ' ')",
        "TIMESTAMPDIFF(DAY, orderDate, orderDate)",
        # Range (1-2)
        "ROUND(salesAmount)",
        "ROUND(salesAmount, 2)",
        "TRUNC(salesAmount)",
        "TRUNC(salesAmount, 2)",
        # Range (2-3)
        "SUBSTR(name, 1)",
        "SUBSTR(name, 1, 3)",
        "SUBSTRING(name, 1)",
        "SUBSTRING(name, 1, 3)",
        "LOCATE('x', name)",
        "LOCATE('x', name, 1)",
        # Unlimited
        "COALESCE(salesAmount, 0)",
        "COALESCE(salesAmount, 0, -1, -99)",
        "CONCAT(name)",
        "CONCAT(name, '_', status)",
        "CONCAT_WS(',', name, status)",
        "CONCAT_WS(',', name, status, 'extra')",
        "GROUP_CONCAT(name)",
        # Aggregation
        "SUM(salesAmount)",
        "AVG(salesAmount)",
        "MIN(salesAmount)",
        "MAX(salesAmount)",
        "COUNT(salesAmount)",
        # Window with args
        "LAG(salesAmount)",
        "LAG(salesAmount, 1)",
        "LAG(salesAmount, 1, 0)",
        "LEAD(salesAmount)",
        "NTILE(4)",
        "FIRST_VALUE(salesAmount)",
        "LAST_VALUE(salesAmount)",
        # Keyword-delimited — NOT validated by arity table, and that's correct
        "CAST(salesAmount AS INTEGER)",
        "EXTRACT(YEAR FROM orderDate)",
        "CONVERT(salesAmount, CHAR)",
    ])
    def test_accepts(self, svc, model, expr):
        # Must not raise
        svc._resolve_expression_fields(expr, model)


# --------------------------------------------------------------------------- #
# 2. Negative cases — wrong arity, should raise ValueError
# --------------------------------------------------------------------------- #

class TestArityNegative:
    @pytest.mark.parametrize("expr,func_name", [
        # Too few
        ("ABS()", "ABS"),
        ("YEAR()", "YEAR"),
        ("MONTH()", "MONTH"),
        ("IF(1, 2)", "IF"),
        ("IF()", "IF"),
        ("IFNULL(salesAmount)", "IFNULL"),
        ("MOD(salesAmount)", "MOD"),
        ("DATE_FORMAT(orderDate)", "DATE_FORMAT"),
        ("REPLACE(name)", "REPLACE"),
        ("REPLACE(name, 'a')", "REPLACE"),
        ("SUBSTR(name)", "SUBSTR"),
        ("CONCAT()", "CONCAT"),
        ("CONCAT_WS(',')", "CONCAT_WS"),
        ("LPAD(name, 10)", "LPAD"),
        ("TIMESTAMPDIFF(DAY, orderDate)", "TIMESTAMPDIFF"),
        # Too many
        ("ABS(salesAmount, 2)", "ABS"),
        ("YEAR(orderDate, extra)", "YEAR"),
        ("ROUND(salesAmount, 2, 3)", "ROUND"),
        ("ROUND(salesAmount, 2, 3, 4)", "ROUND"),
        ("TRUNC(salesAmount, 2, 3)", "TRUNC"),
        ("IFNULL(salesAmount, 0, 1)", "IFNULL"),
        ("MOD(salesAmount, 10, 100)", "MOD"),
        ("IF(1, 2, 3, 4)", "IF"),
        ("SUBSTR(name, 1, 3, 5)", "SUBSTR"),
        ("REPLACE(name, 'a', 'b', 'c')", "REPLACE"),
        ("LAG(salesAmount, 1, 0, 5)", "LAG"),
        # Zero-arg functions — extra args rejected
        ("RANK(extra)", "RANK"),
        ("ROW_NUMBER(extra)", "ROW_NUMBER"),
        ("CURRENT_TIMESTAMP(extra)", "CURRENT_TIMESTAMP"),
    ])
    def test_rejects(self, svc, model, expr, func_name):
        with pytest.raises(ValueError) as ei:
            svc._resolve_expression_fields(expr, model)
        # Error message should mention the function name
        assert func_name in str(ei.value)
        assert "arguments" in str(ei.value) or "argument" in str(ei.value)


class TestArityErrorMessage:
    """Friendly error messages — exact wording contract."""

    def test_too_few_fixed_arity(self, svc, model):
        with pytest.raises(ValueError, match=r"IF.*exactly 3.*got 1"):
            svc._resolve_expression_fields("IF(true)", model)

    def test_too_few_range(self, svc, model):
        with pytest.raises(ValueError, match=r"ROUND.*1 to 2.*got 0"):
            svc._resolve_expression_fields("ROUND()", model)

    def test_too_many_range(self, svc, model):
        with pytest.raises(ValueError, match=r"ROUND.*1 to 2.*got 3"):
            svc._resolve_expression_fields("ROUND(salesAmount, 2, 3)", model)

    def test_too_few_unlimited(self, svc, model):
        with pytest.raises(ValueError, match=r"CONCAT.*1 or more.*got 0"):
            svc._resolve_expression_fields("CONCAT()", model)

    def test_singular_plural(self, svc, model):
        """Check singular/plural grammar: '1 argument' vs '2 arguments'."""
        with pytest.raises(ValueError, match=r"got 1 argument\b"):
            svc._resolve_expression_fields("IF(true)", model)
        with pytest.raises(ValueError, match=r"got 2 arguments\b"):
            svc._resolve_expression_fields("YEAR(a, b)", model)


class TestKeywordDelimitedFunctionsBypass:
    """CAST / CONVERT / EXTRACT have keyword-internal syntax → arity by comma
    is meaningless, must not trigger validation."""

    def test_cast_with_as(self, svc, model):
        # CAST(x AS INT) splits to 1 comma-arg; must not fail even if _FUNCTION_ARITY had a stale entry
        svc._resolve_expression_fields("CAST(salesAmount AS INTEGER)", model)

    def test_extract_with_from(self, svc, model):
        svc._resolve_expression_fields("EXTRACT(YEAR FROM orderDate)", model)

    def test_convert_two_arg_form(self, svc, model):
        svc._resolve_expression_fields("CONVERT(salesAmount, CHAR)", model)


class TestNestedArityValidation:
    """Arity is validated recursively — nested bad call should still fail."""

    def test_nested_bad_call_in_if_branch(self, svc, model):
        with pytest.raises(ValueError, match="YEAR.*got 0"):
            svc._resolve_expression_fields(
                "if(status == 'a', YEAR(), 0)", model
            )

    def test_nested_bad_call_in_coalesce(self, svc, model):
        with pytest.raises(ValueError, match="ROUND.*got 3"):
            svc._resolve_expression_fields(
                "COALESCE(ROUND(salesAmount, 2, 3), 0)", model
            )
