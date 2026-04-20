"""SQL 风格 `v in (...)` / `v not in (...)` 成员测试算子的单元测试。

契约对齐 Java `foggy-fsscript` 8.1.11.beta:
  - IN.java#containsMember / looseEquals
  - NOT_IN.java
  - docs/8.1.11.beta/P2-fsscript支持in和not-in算子-需求.md

Python 侧需求文档：
  - docs/v1.4/P2-fsscript-in-notin算子对齐Java-需求.md
"""

from decimal import Decimal

import pytest

from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.expressions.control_flow import ReturnException
from foggy.fsscript.expressions.operators import (
    BinaryOperator,
    _check_in,
    _loose_equal,
)
from foggy.fsscript.parser import FsscriptParser


# --------------------------------------------------------------------------- #
# 帮助函数
# --------------------------------------------------------------------------- #

def run_expr(src: str, context: dict | None = None):
    """Parse + eval an fsscript source, return the final value."""
    parser = FsscriptParser(src)
    ast = parser.parse_program()
    evaluator = ExpressionEvaluator(context or {})
    return evaluator.evaluate(ast)


def check_exp(src: str, expected, context: dict | None = None):
    got = run_expr(src, context)
    assert got == expected, (
        f"Expression: {src!r}\nExpected: {expected!r}\nGot: {got!r}"
    )


# --------------------------------------------------------------------------- #
# 1. 基本真值
# --------------------------------------------------------------------------- #

class TestInBasic:
    """SQL 风格括号成员测试的主路径。"""

    def test_number_hit(self):
        check_exp("2 in (1, 2, 3)", True)

    def test_number_miss(self):
        check_exp("5 in (1, 2, 3)", False)

    def test_string_hit(self):
        check_exp("'Apple' in ('Apple', 'Huawei', 'Xiaomi')", True)

    def test_string_miss(self):
        check_exp("'OEM' in ('Apple', 'Huawei', 'Xiaomi')", False)

    def test_single_element(self):
        check_exp("7 in (7)", True)

    def test_single_element_miss(self):
        check_exp("8 in (7)", False)

    def test_expression_left(self):
        check_exp("(1 + 1) in (1, 2, 3)", True)

    def test_nested_expression_right(self):
        check_exp("2 in (1, 1 + 1, 3)", True)


class TestNotInBasic:
    """`not in` 对称语义。"""

    def test_miss_becomes_true(self):
        check_exp("5 not in (1, 2, 3)", True)

    def test_hit_becomes_false(self):
        check_exp("2 not in (1, 2, 3)", False)

    def test_string_not_in(self):
        check_exp("'OEM' not in ('Apple', 'Huawei', 'Xiaomi')", True)


# --------------------------------------------------------------------------- #
# 2. 数组字面量 / 变量 / 表达式 RHS
# --------------------------------------------------------------------------- #

class TestInArrayLiteral:
    """`[...]` 数组字面量作为 RHS。"""

    def test_array_literal_hit(self):
        check_exp("2 in [1, 2, 3]", True)

    def test_array_literal_miss(self):
        check_exp("5 in [1, 2, 3]", False)

    def test_not_in_array_literal(self):
        check_exp("5 not in [1, 2, 3]", True)


class TestInVariable:
    """变量 / 调用 / 成员访问 RHS（对齐 Java `x in someList`）。"""

    def test_variable_list(self):
        check_exp("x in arr", True, {"x": 2, "arr": [1, 2, 3]})

    def test_variable_list_miss(self):
        check_exp("x in arr", False, {"x": 5, "arr": [1, 2, 3]})

    def test_variable_tuple(self):
        check_exp("x in arr", True, {"x": 2, "arr": (1, 2, 3)})

    def test_variable_set(self):
        check_exp("x in arr", True, {"x": 2, "arr": {1, 2, 3}})

    def test_variable_dict_uses_keys(self):
        """`v in dict` 使用 dict keys（对齐 Java Map.keySet）。"""
        check_exp(
            "k in m", True,
            {"k": "a", "m": {"a": 1, "b": 2}},
        )
        check_exp(
            "k in m", False,
            {"k": "z", "m": {"a": 1, "b": 2}},
        )

    def test_variable_scalar_singleton_semantics(self):
        """标量 RHS 按 Java singleton 语义包装。"""
        check_exp("x in y", True, {"x": 5, "y": 5})
        check_exp("x in y", False, {"x": 5, "y": 6})


class TestInMember:
    """`v in a.b` 成员访问 RHS（回归：_parse_in_rhs 兜底走常规表达式）。"""

    def test_member_access_rhs(self):
        check_exp(
            "x in obj.items", True,
            {"x": 2, "obj": {"items": [1, 2, 3]}},
        )


# --------------------------------------------------------------------------- #
# 3. null / 空集合
# --------------------------------------------------------------------------- #

class TestInNull:
    """null 语义对齐 Java `IN.looseEquals`。"""

    def test_null_in_with_null_element(self):
        check_exp("null in (1, null, 2)", True)

    def test_null_in_without_null_element(self):
        check_exp("null in (1, 2)", False)

    def test_value_in_null(self):
        """右侧 null 返回 false（对齐 Java resolveHaystack 返回 null）。"""
        check_exp("x in y", False, {"x": 1, "y": None})

    def test_empty_parens_never_contains(self):
        check_exp("1 in ()", False)

    def test_empty_parens_not_in(self):
        check_exp("1 not in ()", True)

    def test_empty_array_literal(self):
        check_exp("1 in []", False)


# --------------------------------------------------------------------------- #
# 4. 数值归一（对齐 Java BigDecimal.compareTo）
# --------------------------------------------------------------------------- #

class TestInNumericEquivalence:
    """Number 之间通过 Decimal 归一。"""

    def test_int_vs_float(self):
        check_exp("1 in (1.0, 2.0)", True)

    def test_float_vs_int(self):
        check_exp("1.0 in (1, 2)", True)

    def test_int_vs_decimal_via_context(self):
        check_exp(
            "x in arr", True,
            {"x": 1, "arr": [Decimal("1"), Decimal("2")]},
        )

    def test_cross_type_still_distinct(self):
        """跨类型（字符串 vs 数字）不归一。"""
        check_exp("1 in ('1', '2')", False)


# --------------------------------------------------------------------------- #
# 5. bool 护栏（Python 特有，Java 无此陷阱）
# --------------------------------------------------------------------------- #

class TestInBoolGuard:
    """Python 中 `bool` 是 `int` 子类 → 必须阻断 True == 1 的意外命中。"""

    def test_true_not_member_of_numeric_list(self):
        check_exp("true in (1, 2)", False)

    def test_false_not_member_of_numeric_list(self):
        check_exp("false in (0, 1)", False)

    def test_number_not_member_of_bool_list(self):
        check_exp("1 in (true, false)", False)

    def test_bool_vs_bool_still_works(self):
        check_exp("true in (true, false)", True)
        check_exp("false in (true)", False)


# --------------------------------------------------------------------------- #
# 6. 字符串 haystack
# --------------------------------------------------------------------------- #

class TestInString:
    """字符串作为 haystack：Python 原生子串语义。"""

    def test_substring_hit(self):
        check_exp("'e' in 'hello'", True)

    def test_substring_miss(self):
        check_exp("'z' in 'hello'", False)

    def test_multichar_substring(self):
        check_exp("'ell' in 'hello'", True)


# --------------------------------------------------------------------------- #
# 7. 尾随逗号
# --------------------------------------------------------------------------- #

class TestInTrailingComma:
    """`(1, 2, 3,)` 尾随逗号宽松兼容。"""

    def test_trailing_comma_allowed(self):
        check_exp("2 in (1, 2, 3,)", True)


# --------------------------------------------------------------------------- #
# 8. 回归：相关现有语法不受影响
# --------------------------------------------------------------------------- #

class TestRegression:
    """保证 for-in / instanceof / 前缀 not / == 等未受 NOT IN lookahead 影响。"""

    def test_for_in_still_parses(self):
        """for-in 循环走独立 parser 分支，不受中缀 IN 影响。"""
        src = (
            "var arr = [10, 20, 30];"
            "var flag = false;"
            "for (var i in arr) { if (i == 1) { flag = true; } }"
            "return flag;"
        )
        parser = FsscriptParser(src)
        ast = parser.parse_program()
        with pytest.raises(ReturnException) as exc:
            ExpressionEvaluator({}).evaluate(ast)
        assert exc.value.value is True

    def test_prefix_not_boolean(self):
        check_exp("not true", False)
        check_exp("not false", True)

    def test_prefix_not_on_expression(self):
        check_exp("not (1 == 2)", True)

    def test_prefix_not_before_identifier_not_consumed_as_not_in(self):
        """确保 `x && not y` 里的 `not` 不会误吃下一 token 的 IN。"""
        check_exp("x && not y", True, {"x": 1, "y": False})

    def test_instanceof_still_works(self):
        check_exp("[1, 2, 3] instanceof Array", True)

    def test_equality_still_works(self):
        check_exp("1 == 1", True)
        check_exp("1 != 2", True)


# --------------------------------------------------------------------------- #
# 9. AST 形状（enum + helper 直接单测）
# --------------------------------------------------------------------------- #

class TestOperatorEnum:
    def test_in_enum_value(self):
        assert BinaryOperator.IN.value == "in"

    def test_not_in_enum_value(self):
        assert BinaryOperator.NOT_IN.value == "not in"


class TestCheckInDirect:
    """_check_in 的模块级单测（解耦 parser，锁定语义契约）。"""

    def test_basic(self):
        assert _check_in(2, [1, 2, 3]) is True
        assert _check_in(5, [1, 2, 3]) is False

    def test_none_haystack(self):
        assert _check_in(1, None) is False

    def test_dict_uses_keys(self):
        assert _check_in("a", {"a": 1, "b": 2}) is True
        assert _check_in("z", {"a": 1, "b": 2}) is False

    def test_scalar_singleton(self):
        assert _check_in(5, 5) is True
        assert _check_in(5, 6) is False

    def test_tuple_haystack(self):
        assert _check_in(2, (1, 2, 3)) is True

    def test_set_haystack(self):
        assert _check_in(2, {1, 2, 3}) is True


class TestLooseEqualDirect:
    def test_null_null(self):
        assert _loose_equal(None, None) is True

    def test_null_anything(self):
        assert _loose_equal(None, 0) is False
        assert _loose_equal(0, None) is False

    def test_int_float(self):
        assert _loose_equal(1, 1.0) is True

    def test_int_decimal(self):
        assert _loose_equal(1, Decimal("1.0")) is True

    def test_bool_vs_int(self):
        assert _loose_equal(True, 1) is False
        assert _loose_equal(1, True) is False

    def test_bool_vs_bool(self):
        assert _loose_equal(True, True) is True
        assert _loose_equal(False, False) is True
        assert _loose_equal(True, False) is False

    def test_string_equal(self):
        assert _loose_equal("a", "a") is True
        assert _loose_equal("a", "b") is False
