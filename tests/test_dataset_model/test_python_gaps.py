"""Tests for PYTHON_GAPS.md features — operators, function whitelist, $field references.

Covers:
- P0: not like / not left_like / not right_like
- P0: isNullAndEmpty / isNotNullAndEmpty
- P1: force_eq (===)
- P1: bit_in
- P1: Function whitelist
- P2: $field value reference
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.formula import (
    NotLikeFormula,
    NotLeftLikeFormula,
    NotRightLikeFormula,
    IsNullAndEmptyFormula,
    IsNotNullAndEmptyFormula,
    ForceEqFormula,
    BitInFormula,
    get_default_registry,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.impl.model import DbTableModelImpl, DbModelDimensionImpl, DbModelMeasureImpl
from foggy.dataset_model.definitions.base import AggregationType
from foggy.mcp_spi import SemanticQueryRequest


# ==================== Helper ====================


def _make_test_model() -> DbTableModelImpl:
    """Create a minimal model for filter/query tests."""
    model = DbTableModelImpl(name="TestModel", source_table="t_test")
    model.add_dimension(DbModelDimensionImpl(name="status", column="status"))
    model.add_dimension(DbModelDimensionImpl(name="name", column="name"))
    model.add_measure(DbModelMeasureImpl(
        name="salesAmount", column="sales_amount", aggregation=AggregationType.SUM,
    ))
    model.add_measure(DbModelMeasureImpl(
        name="costAmount", column="cost_amount", aggregation=AggregationType.SUM,
    ))
    return model


def _build_sql(model_name: str, request: SemanticQueryRequest, svc: SemanticQueryService) -> str:
    r = svc.query_model(model_name, request, mode="validate")
    assert r.error is None, f"Query failed: {r.error}"
    return r.sql


# ==================== P0: NOT LIKE ====================


class TestNotLikeFormula:
    def test_not_like(self):
        params = []
        sql = NotLikeFormula().build_condition("t.name", "not like", "test", params)
        assert sql == "t.name NOT LIKE ?"
        assert params == ["%test%"]

    def test_not_left_like(self):
        params = []
        sql = NotLeftLikeFormula().build_condition("t.name", "not left_like", "abc", params)
        assert sql == "t.name NOT LIKE ?"
        assert params == ["abc%"]

    def test_not_right_like(self):
        params = []
        sql = NotRightLikeFormula().build_condition("t.name", "not right_like", "xyz", params)
        assert sql == "t.name NOT LIKE ?"
        assert params == ["%xyz"]


class TestNotLikeRegistry:
    """Verify NOT LIKE variants are registered in default registry."""

    @pytest.fixture
    def reg(self):
        return get_default_registry()

    def test_not_like_registered(self, reg):
        assert "not like" in reg
        assert "not_like" in reg

    def test_not_left_like_registered(self, reg):
        assert "not left_like" in reg
        assert "not_left_like" in reg

    def test_not_right_like_registered(self, reg):
        assert "not right_like" in reg
        assert "not_right_like" in reg

    def test_not_like_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.city", "not like", "York", params)
        assert sql == "t.city NOT LIKE ?"
        assert params == ["%York%"]

    def test_not_left_like_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.code", "not_left_like", "AB", params)
        assert sql == "t.code NOT LIKE ?"
        assert params == ["AB%"]

    def test_not_right_like_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.name", "not_right_like", "son", params)
        assert sql == "t.name NOT LIKE ?"
        assert params == ["%son"]


class TestNotLikeInQuery:
    """Integration: NOT LIKE in a SemanticQueryService filter."""

    def test_not_like_filter(self):
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["name$caption"],
            slice=[{"field": "name", "op": "not like", "value": "test"}],
            limit=10,
        ), mode="validate")

        assert r.error is None
        assert "NOT LIKE" in r.sql


# ==================== P0: isNullAndEmpty / isNotNullAndEmpty ====================


class TestIsNullAndEmptyFormula:
    def test_is_null_and_empty(self):
        params = []
        sql = IsNullAndEmptyFormula().build_condition("t.email", "isNullAndEmpty", None, params)
        assert sql == "(t.email IS NULL OR t.email = '')"
        assert params == []

    def test_is_not_null_and_empty(self):
        params = []
        sql = IsNotNullAndEmptyFormula().build_condition("t.email", "isNotNullAndEmpty", None, params)
        assert sql == "(t.email IS NOT NULL AND t.email <> '')"
        assert params == []


class TestNullAndEmptyRegistry:
    @pytest.fixture
    def reg(self):
        return get_default_registry()

    def test_is_null_and_empty_registered(self, reg):
        assert "isNullAndEmpty" in reg
        assert "is_null_and_empty" in reg

    def test_is_not_null_and_empty_registered(self, reg):
        assert "isNotNullAndEmpty" in reg
        assert "is_not_null_and_empty" in reg

    def test_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.email", "isNullAndEmpty", None, params)
        assert "IS NULL" in sql
        assert "= ''" in sql


class TestNullAndEmptyInQuery:
    def test_is_null_and_empty_filter(self):
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["name$caption"],
            slice=[{"field": "status", "op": "isNullAndEmpty"}],
            limit=10,
        ), mode="validate")

        assert r.error is None
        assert "IS NULL" in r.sql
        assert "= ''" in r.sql

    def test_is_not_null_and_empty_filter(self):
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["name$caption"],
            slice=[{"field": "status", "op": "isNotNullAndEmpty"}],
            limit=10,
        ), mode="validate")

        assert r.error is None
        assert "IS NOT NULL" in r.sql
        assert "<> ''" in r.sql


# ==================== P1: force_eq (===) ====================


class TestForceEqFormula:
    def test_force_eq(self):
        params = []
        sql = ForceEqFormula().build_condition("t.code", "===", "ABC", params)
        assert sql == "t.code = ?"
        assert params == ["ABC"]

    def test_force_eq_numeric(self):
        params = []
        sql = ForceEqFormula().build_condition("t.id", "===", 0, params)
        assert sql == "t.id = ?"
        assert params == [0]


class TestForceEqRegistry:
    @pytest.fixture
    def reg(self):
        return get_default_registry()

    def test_triple_eq_registered(self, reg):
        assert "===" in reg

    def test_force_eq_alias_registered(self, reg):
        assert "force_eq" in reg

    def test_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.flag", "===", 0, params)
        assert sql == "t.flag = ?"
        assert params == [0]


# ==================== P1: bit_in ====================


class TestBitInFormula:
    def test_bit_in(self):
        params = []
        sql = BitInFormula().build_condition("t.permissions", "bit_in", 4, params)
        assert sql == "(t.permissions & ?) = ?"
        assert params == [4, 4]

    def test_bit_in_large_flag(self):
        params = []
        sql = BitInFormula().build_condition("t.flags", "bit_in", 0xFF, params)
        assert sql == "(t.flags & ?) = ?"
        assert params == [255, 255]


class TestBitInRegistry:
    @pytest.fixture
    def reg(self):
        return get_default_registry()

    def test_bit_in_registered(self, reg):
        assert "bit_in" in reg

    def test_via_registry(self, reg):
        params = []
        sql = reg.build_condition("t.mask", "bit_in", 8, params)
        assert "(t.mask & ?) = ?" == sql
        assert params == [8, 8]


# ==================== P1: Function Whitelist ====================


class TestFunctionWhitelist:
    """Verify function whitelist enforcement."""

    def test_allowed_function_sum(self):
        assert SemanticQueryService.validate_function("SUM") is True

    def test_allowed_function_case_insensitive(self):
        assert SemanticQueryService.validate_function("sum") is True
        assert SemanticQueryService.validate_function("Concat_ws") is True

    def test_allowed_window_functions(self):
        for fn in ["ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE"]:
            assert SemanticQueryService.validate_function(fn) is True, f"{fn} should be allowed"

    def test_allowed_statistical_functions(self):
        for fn in ["STDDEV_POP", "STDDEV_SAMP", "VAR_POP", "VAR_SAMP"]:
            assert SemanticQueryService.validate_function(fn) is True, f"{fn} should be allowed"

    def test_allowed_string_functions(self):
        for fn in ["CONCAT_WS", "SUBSTR", "LEFT", "RIGHT", "LTRIM", "RTRIM", "CHAR_LENGTH", "REPLACE", "LPAD", "RPAD"]:
            assert SemanticQueryService.validate_function(fn) is True, f"{fn} should be allowed"

    def test_allowed_date_functions(self):
        for fn in ["HOUR", "MINUTE", "SECOND", "TIME", "CURRENT_TIME", "CURRENT_TIMESTAMP", "TIMESTAMPDIFF", "DATE_FORMAT", "STR_TO_DATE", "EXTRACT"]:
            assert SemanticQueryService.validate_function(fn) is True, f"{fn} should be allowed"

    def test_allowed_conditional_functions(self):
        for fn in ["NVL", "ISNULL", "IF", "CAST", "CONVERT", "COALESCE"]:
            assert SemanticQueryService.validate_function(fn) is True, f"{fn} should be allowed"

    def test_disallowed_function(self):
        assert SemanticQueryService.validate_function("SLEEP") is False
        assert SemanticQueryService.validate_function("LOAD_FILE") is False
        assert SemanticQueryService.validate_function("BENCHMARK") is False

    def test_disallowed_dangerous_functions(self):
        for fn in ["SYSTEM", "EXEC", "xp_cmdshell", "DROP", "DELETE", "TRUNCATE"]:
            assert SemanticQueryService.validate_function(fn) is False, f"{fn} should be blocked"

    def test_whitelist_rejects_in_expression(self):
        """Disallowed function in a calculated field expression should raise ValueError."""
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        with pytest.raises(ValueError, match="not in the allowed function whitelist"):
            svc._resolve_expression_fields("SLEEP(5)", model)

    def test_whitelist_allows_valid_expression(self):
        """Allowed function in expression should work."""
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        # SUM is allowed, salesAmount resolves to t.sales_amount
        result = svc._resolve_expression_fields("SUM(salesAmount)", model)
        assert "SUM" in result
        assert "sales_amount" in result


# ==================== P2: $field Value Reference ====================


class TestFieldReference:
    """$field value reference in filter conditions."""

    def test_field_reference_gt(self):
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["salesAmount", "costAmount"],
            slice=[{"field": "salesAmount", "op": ">", "value": {"$field": "costAmount"}}],
        ), mode="validate")

        assert r.error is None
        # Should have field-to-field comparison: t.sales_amount > t.cost_amount
        assert "sales_amount" in r.sql
        assert "cost_amount" in r.sql
        assert ">" in r.sql

    def test_field_reference_eq(self):
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["name$caption"],
            slice=[{"field": "name", "op": "=", "value": {"$field": "status"}}],
        ), mode="validate")

        assert r.error is None
        assert "t.name" in r.sql
        assert "t.status" in r.sql

    def test_field_reference_no_bind_params(self):
        """$field comparison should not add bind parameters."""
        model = _make_test_model()
        svc = SemanticQueryService()
        svc.register_model(model)

        r = svc.query_model("TestModel", SemanticQueryRequest(
            columns=["salesAmount"],
            slice=[{"field": "salesAmount", "op": ">=", "value": {"$field": "costAmount"}}],
        ), mode="validate")

        assert r.error is None
        # SQL should contain direct comparison, no ?
        assert "?" not in r.sql.split("WHERE")[1] if "WHERE" in r.sql else True


# ==================== Registry Completeness ====================


class TestRegistryCompleteness:
    """Verify the default registry has all expected operators."""

    def test_total_operator_count(self):
        reg = get_default_registry()
        # 15 original + 6 not-like + 4 null-empty + 2 force-eq + 1 bit-in = 28+
        assert len(reg) >= 28

    def test_all_gap_operators_present(self):
        reg = get_default_registry()
        gap_operators = [
            "not like", "not_like",
            "not left_like", "not_left_like",
            "not right_like", "not_right_like",
            "isNullAndEmpty", "is_null_and_empty",
            "isNotNullAndEmpty", "is_not_null_and_empty",
            "===", "force_eq",
            "bit_in",
        ]
        for op in gap_operators:
            assert op in reg, f"Operator '{op}' missing from registry"
