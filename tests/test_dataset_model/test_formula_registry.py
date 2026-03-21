"""Tests for SqlFormula system (engine/formula/).

25+ tests covering every operator and registry behaviour.
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.formula import (
    BetweenFormula,
    EqFormula,
    GtFormula,
    GteFormula,
    InFormula,
    IsNotNullFormula,
    IsNullFormula,
    LeftLikeFormula,
    LikeFormula,
    LtFormula,
    LteFormula,
    NotEqFormula,
    NotInFormula,
    RangeFormula,
    RightLikeFormula,
    SqlFormulaRegistry,
    get_default_registry,
)


# ===================================================================
# TestSqlFormula — individual operator classes
# ===================================================================

class TestEqFormula:
    def test_eq(self):
        params: list = []
        sql = EqFormula().build_condition("t.id", "=", 42, params)
        assert sql == "t.id = ?"
        assert params == [42]

    def test_eq_string(self):
        params: list = []
        sql = EqFormula().build_condition("t.name", "=", "Alice", params)
        assert sql == "t.name = ?"
        assert params == ["Alice"]


class TestNotEqFormula:
    def test_neq_bang(self):
        params: list = []
        sql = NotEqFormula().build_condition("t.status", "!=", "closed", params)
        assert sql == "t.status <> ?"
        assert params == ["closed"]

    def test_neq_diamond(self):
        params: list = []
        sql = NotEqFormula().build_condition("t.status", "<>", "closed", params)
        assert sql == "t.status <> ?"
        assert params == ["closed"]


class TestGtFormula:
    def test_gt(self):
        params: list = []
        sql = GtFormula().build_condition("t.price", ">", 100, params)
        assert sql == "t.price > ?"
        assert params == [100]


class TestGteFormula:
    def test_gte(self):
        params: list = []
        sql = GteFormula().build_condition("t.price", ">=", 100, params)
        assert sql == "t.price >= ?"
        assert params == [100]


class TestLtFormula:
    def test_lt(self):
        params: list = []
        sql = LtFormula().build_condition("t.qty", "<", 5, params)
        assert sql == "t.qty < ?"
        assert params == [5]


class TestLteFormula:
    def test_lte(self):
        params: list = []
        sql = LteFormula().build_condition("t.qty", "<=", 5, params)
        assert sql == "t.qty <= ?"
        assert params == [5]


class TestInFormula:
    def test_in_list(self):
        params: list = []
        sql = InFormula().build_condition("t.id", "in", [1, 2, 3], params)
        assert sql == "t.id IN (?, ?, ?)"
        assert params == [1, 2, 3]

    def test_in_single_value_wrapped(self):
        params: list = []
        sql = InFormula().build_condition("t.id", "in", 99, params)
        assert sql == "t.id IN (?)"
        assert params == [99]

    def test_in_tuple(self):
        params: list = []
        sql = InFormula().build_condition("t.id", "in", (10, 20), params)
        assert sql == "t.id IN (?, ?)"
        assert params == [10, 20]


class TestNotInFormula:
    def test_not_in(self):
        params: list = []
        sql = NotInFormula().build_condition("t.id", "not in", [4, 5], params)
        assert sql == "t.id NOT IN (?, ?)"
        assert params == [4, 5]

    def test_nin_alias(self):
        params: list = []
        sql = NotInFormula().build_condition("t.id", "nin", [6], params)
        assert sql == "t.id NOT IN (?)"
        assert params == [6]


class TestLikeFormula:
    def test_like_wraps_percent(self):
        params: list = []
        sql = LikeFormula().build_condition("t.name", "like", "foo", params)
        assert sql == "t.name LIKE ?"
        assert params == ["%foo%"]


class TestLeftLikeFormula:
    def test_left_like(self):
        params: list = []
        sql = LeftLikeFormula().build_condition("t.name", "left_like", "foo", params)
        assert sql == "t.name LIKE ?"
        assert params == ["foo%"]


class TestRightLikeFormula:
    def test_right_like(self):
        params: list = []
        sql = RightLikeFormula().build_condition("t.name", "right_like", "bar", params)
        assert sql == "t.name LIKE ?"
        assert params == ["%bar"]


class TestIsNullFormula:
    def test_is_null(self):
        params: list = []
        sql = IsNullFormula().build_condition("t.deleted_at", "is null", None, params)
        assert sql == "t.deleted_at IS NULL"
        assert params == []

    def test_is_null_ignores_value(self):
        params: list = []
        sql = IsNullFormula().build_condition("t.x", "isNull", "anything", params)
        assert sql == "t.x IS NULL"
        assert params == []


class TestIsNotNullFormula:
    def test_is_not_null(self):
        params: list = []
        sql = IsNotNullFormula().build_condition("t.email", "is not null", None, params)
        assert sql == "t.email IS NOT NULL"
        assert params == []

    def test_is_not_null_alias(self):
        params: list = []
        sql = IsNotNullFormula().build_condition("t.email", "isNotNull", None, params)
        assert sql == "t.email IS NOT NULL"
        assert params == []


class TestRangeFormula:
    def test_range_closed(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "[]", [10, 20], params)
        assert sql == "t.price >= ? AND t.price <= ?"
        assert params == [10, 20]

    def test_range_left_open(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "(]", [10, 20], params)
        assert sql == "t.price > ? AND t.price <= ?"
        assert params == [10, 20]

    def test_range_right_open(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "[)", [10, 20], params)
        assert sql == "t.price >= ? AND t.price < ?"
        assert params == [10, 20]

    def test_range_open(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "()", [10, 20], params)
        assert sql == "t.price > ? AND t.price < ?"
        assert params == [10, 20]

    def test_range_invalid_value(self):
        with pytest.raises(ValueError, match="requires a \\[start, end\\] list"):
            RangeFormula().build_condition("t.x", "[]", 42, [])

    def test_range_none_start(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "[]", [None, 100], params)
        assert sql == "t.price <= ?"
        assert params == [100]

    def test_range_none_end(self):
        params: list = []
        sql = RangeFormula().build_condition("t.price", "[]", [50, None], params)
        assert sql == "t.price >= ?"
        assert params == [50]


class TestBetweenFormula:
    def test_between(self):
        params: list = []
        sql = BetweenFormula().build_condition("t.date", "between", ["2024-01-01", "2024-12-31"], params)
        assert sql == "t.date BETWEEN ? AND ?"
        assert params == ["2024-01-01", "2024-12-31"]

    def test_between_invalid(self):
        with pytest.raises(ValueError, match="requires a \\[start, end\\] list"):
            BetweenFormula().build_condition("t.x", "between", "nope", [])


# ===================================================================
# TestSqlFormulaRegistry
# ===================================================================

class TestSqlFormulaRegistry:
    def test_default_registry_contains_all_operators(self):
        reg = get_default_registry()
        for op in ("=", "eq", "!=", "<>", ">", ">=", "<", "<=",
                    "in", "not in", "nin", "like", "left_like", "right_like",
                    "is null", "isNull", "is not null", "isNotNull",
                    "[]", "[)", "(]", "()", "between"):
            assert op in reg, f"operator {op!r} not registered"

    def test_registry_build_condition(self):
        reg = get_default_registry()
        params: list = []
        sql = reg.build_condition("t.id", "=", 1, params)
        assert sql == "t.id = ?"
        assert params == [1]

    def test_registry_unknown_operator(self):
        reg = get_default_registry()
        with pytest.raises(KeyError, match="Unknown operator"):
            reg.build_condition("t.x", "XYZZY", 1, [])

    def test_registry_len(self):
        reg = get_default_registry()
        assert len(reg) >= 20  # many aliases

    def test_registry_operators_sorted(self):
        reg = get_default_registry()
        ops = reg.operators
        assert ops == sorted(ops)

    def test_custom_registry(self):
        reg = SqlFormulaRegistry()
        reg.register("=", EqFormula())
        assert "=" in reg
        assert len(reg) == 1

    def test_get_returns_none_for_missing(self):
        reg = SqlFormulaRegistry()
        assert reg.get("missing") is None
