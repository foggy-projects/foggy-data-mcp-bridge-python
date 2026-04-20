"""Operator expressions (binary and unary)."""

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, Iterable, Optional
from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class BinaryOperator(str, Enum):
    """Binary operators."""

    # Arithmetic
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    POWER = "**"

    # Comparison
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="

    # Logical
    AND = "&&"
    OR = "||"

    # String
    CONCAT = "++"

    # Null-safe
    NULL_COALESCE = "??"

    # Type check
    INSTANCEOF = "instanceof"

    # Membership (SQL-style `v in (...)` / `v not in (...)`)
    # 契约对齐 Java `foggy-fsscript` 8.1.11.beta
    # `IN.java` / `NOT_IN.java` 的 containsMember + looseEquals 语义。
    IN = "in"
    NOT_IN = "not in"


class UnaryOperator(str, Enum):
    """Unary operators."""

    NEGATE = "-"
    NOT = "!"
    BITWISE_NOT = "~"
    TYPEOF = "typeof"


class BinaryExpression(Expression):
    """Binary operation expression (e.g., a + b, x == y)."""

    left: Expression = Field(..., description="Left operand")
    operator: BinaryOperator = Field(..., description="Operator")
    right: Expression = Field(..., description="Right operand")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate the binary operation."""
        left_val = self.left.evaluate(context)
        right_val = self.right.evaluate(context)

        op = self.operator

        # Arithmetic
        if op == BinaryOperator.ADD:
            return self._add(left_val, right_val)
        elif op == BinaryOperator.SUBTRACT:
            return self._to_number(left_val) - self._to_number(right_val)
        elif op == BinaryOperator.MULTIPLY:
            return self._to_number(left_val) * self._to_number(right_val)
        elif op == BinaryOperator.DIVIDE:
            right = self._to_number(right_val)
            if right == 0:
                return None  # Division by zero returns null
            return self._to_number(left_val) / right
        elif op == BinaryOperator.MODULO:
            right = self._to_number(right_val)
            if right == 0:
                return None
            return self._to_number(left_val) % right
        elif op == BinaryOperator.POWER:
            return self._to_number(left_val) ** self._to_number(right_val)

        # Comparison
        elif op == BinaryOperator.EQUAL:
            return left_val == right_val
        elif op == BinaryOperator.NOT_EQUAL:
            return left_val != right_val
        elif op == BinaryOperator.LESS:
            return self._compare(left_val, right_val) < 0
        elif op == BinaryOperator.LESS_EQUAL:
            return self._compare(left_val, right_val) <= 0
        elif op == BinaryOperator.GREATER:
            return self._compare(left_val, right_val) > 0
        elif op == BinaryOperator.GREATER_EQUAL:
            return self._compare(left_val, right_val) >= 0

        # Logical — JavaScript semantics: return actual operand, not bool
        elif op == BinaryOperator.AND:
            return left_val if not self._to_bool(left_val) else right_val
        elif op == BinaryOperator.OR:
            return left_val if self._to_bool(left_val) else right_val

        # String
        elif op == BinaryOperator.CONCAT:
            return self._to_string(left_val) + self._to_string(right_val)

        # Null-safe
        elif op == BinaryOperator.NULL_COALESCE:
            return right_val if left_val is None else left_val

        # Type check
        elif op == BinaryOperator.INSTANCEOF:
            return _check_instanceof(left_val, right_val)

        # Membership (SQL-style)
        elif op == BinaryOperator.IN:
            return _check_in(left_val, right_val)
        elif op == BinaryOperator.NOT_IN:
            return not _check_in(left_val, right_val)

        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_binary(self)

    def _add(self, left: Any, right: Any) -> Any:
        """Add two values (handles numbers and strings)."""
        if isinstance(left, str) or isinstance(right, str):
            return self._to_string(left) + self._to_string(right)
        return self._to_number(left) + self._to_number(right)

    def _to_number(self, value: Any) -> float:
        """Convert to number."""
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True

    def _to_string(self, value: Any) -> str:
        """Convert to string."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _compare(self, left: Any, right: Any) -> int:
        """Compare two values."""
        if left == right:
            return 0
        if left is None:
            return -1
        if right is None:
            return 1
        try:
            if left < right:
                return -1
            elif left > right:
                return 1
            return 0
        except TypeError:
            # Incomparable types
            return 0

    def __repr__(self) -> str:
        return f"({self.left} {self.operator.value} {self.right})"


class UnaryExpression(Expression):
    """Unary operation expression (e.g., -x, !flag)."""

    operator: UnaryOperator = Field(..., description="Operator")
    operand: Expression = Field(..., description="Operand")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate the unary operation."""
        val = self.operand.evaluate(context)

        op = self.operator

        if op == UnaryOperator.NEGATE:
            if isinstance(val, (int, float)):
                return -val
            return 0

        elif op == UnaryOperator.NOT:
            if isinstance(val, bool):
                return not val
            return not self._to_bool(val)

        elif op == UnaryOperator.BITWISE_NOT:
            if isinstance(val, int):
                return ~val
            return 0

        elif op == UnaryOperator.TYPEOF:
            return fsscript_typeof(val)

        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_unary(self)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        return True

    def __repr__(self) -> str:
        return f"({self.operator.value}{self.operand})"


class TernaryExpression(Expression):
    """Ternary/conditional expression (condition ? then : else)."""

    condition: Expression = Field(..., description="Condition")
    then_expr: Expression = Field(..., description="Then expression")
    else_expr: Expression = Field(..., description="Else expression")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate the ternary expression."""
        cond_val = self.condition.evaluate(context)

        if self._to_bool(cond_val):
            return self.then_expr.evaluate(context)
        else:
            return self.else_expr.evaluate(context)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_ternary(self)

    def _to_bool(self, value: Any) -> bool:
        """Convert to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        return True

    def __repr__(self) -> str:
        return f"({self.condition} ? {self.then_expr} : {self.else_expr})"


class UpdateOperator(str, Enum):
    """Update operators for increment/decrement."""

    INCREMENT = "++"
    DECREMENT = "--"


class UpdateExpression(Expression):
    """Update expression for increment/decrement operations.

    Handles both prefix (++x, --x) and postfix (x++, x--) forms.
    """

    operator: UpdateOperator = Field(..., description="Update operator")
    operand: Expression = Field(..., description="Target expression to update")
    prefix: bool = Field(default=False, description="True for prefix (++x), False for postfix (x++)")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate the update expression.

        For prefix: return the new value after update.
        For postfix: return the old value before update.
        """
        # Get the current value
        current_value = self.operand.evaluate(context)

        # Calculate the new value
        if self.operator == UpdateOperator.INCREMENT:
            new_value = current_value + 1 if isinstance(current_value, (int, float)) else 1
        else:  # DECREMENT
            new_value = current_value - 1 if isinstance(current_value, (int, float)) else -1

        # Update the value in context
        from foggy.fsscript.expressions.variables import VariableExpression, MemberAccessExpression, IndexAccessExpression

        if isinstance(self.operand, VariableExpression):
            context[self.operand.name] = new_value
        elif isinstance(self.operand, MemberAccessExpression):
            obj = self.operand.obj.evaluate(context)
            if isinstance(obj, dict):
                obj[self.operand.member] = new_value
        elif isinstance(self.operand, IndexAccessExpression):
            obj = self.operand.obj.evaluate(context)
            index = self.operand.index.evaluate(context)
            if isinstance(obj, (list, dict)):
                obj[index] = new_value

        # Return old value for postfix, new value for prefix
        return new_value if self.prefix else current_value

    def accept(self, visitor: "ExpressionVisitor") -> Any:
        """Accept visitor."""
        return visitor.visit_update(self)

    def __repr__(self) -> str:
        if self.prefix:
            return f"({self.operator.value}{self.operand})"
        return f"({self.operand}{self.operator.value})"


# ---------------------------------------------------------------------------
# typeof / instanceof helpers
# ---------------------------------------------------------------------------

def fsscript_typeof(value: Any) -> str:
    """Return a JS-compatible type string for the given value.

    Matches ECMAScript ``typeof`` semantics:
    - ``undefined`` / ``None``  → ``"undefined"``
    - ``bool``                  → ``"boolean"``
    - ``int`` / ``float``       → ``"number"``
    - ``str``                   → ``"string"``
    - callable                  → ``"function"``
    - everything else           → ``"object"``
    """
    if value is None:
        return "undefined"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if callable(value):
        return "function"
    return "object"


_INSTANCEOF_MAP = {
    "Array": lambda v: isinstance(v, list),
    "Object": lambda v: isinstance(v, dict),
    "Function": lambda v: callable(v),
    "String": lambda v: isinstance(v, str),
    "Number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "Boolean": lambda v: isinstance(v, bool),
}


def _check_instanceof(left_val: Any, right_val: Any) -> bool:
    """Check ``left instanceof Right``.

    *right_val* is resolved from context.  It may be:
    - A Python ``type`` (``list``, ``dict``, …) registered as a builtin
    - A string type-name coming from an unresolved identifier
    """
    # Fast path: right_val is a Python type (registered in builtins)
    if isinstance(right_val, type):
        return isinstance(left_val, right_val)

    # String name lookup (fallback)
    name = None
    if isinstance(right_val, str):
        name = right_val
    elif right_val is not None and hasattr(right_val, "__name__"):
        name = right_val.__name__

    if name and name in _INSTANCEOF_MAP:
        return _INSTANCEOF_MAP[name](left_val)

    return False


# ---------------------------------------------------------------------------
# in / not in helpers
#
# 契约对齐 Java `foggy-fsscript` 8.1.11.beta:
#   - IN.java#containsMember(ee, left, right)          -> _check_in
#   - IN.java#toIterable(v)                            -> _to_haystack
#   - IN.java#looseEquals(a, b) + toBigDecimal(n)      -> _loose_equal
#
# Python 特有的偏差（已加护栏、见 tests/test_fsscript/test_in_operator.py）：
#   - `bool` 是 `int` 的子类；Java 侧 Boolean 与 Number 不会混淆。
#     我们在 _loose_equal 的数值归一路径显式排除 bool，避免
#     `True in (1, 2)` / `1 in (True, False)` 意外为真。
# ---------------------------------------------------------------------------


def _to_haystack(value: Any) -> Optional[Iterable[Any]]:
    """Normalize the right-hand operand to an iterable.

    对齐 Java `IN.toIterable`:
    - None             -> None（调用方按 False 处理）
    - dict             -> keys()
    - list/tuple/set/frozenset/str -> 原样可迭代
    - 其他可迭代对象   -> `list(it)` 一次性物化（避免生成器耗尽）
    - 标量             -> `[value]` 单元素集合
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, (list, tuple, set, frozenset)):
        return value
    if isinstance(value, str):
        # 字符串作为 haystack：沿用 Python 原生 `in` 子串语义。
        # Java singleton 路径下 `"a" in "a"` 也为 true，语义一致。
        return value
    # 其他任意可迭代对象统一物化一次。
    if hasattr(value, "__iter__"):
        try:
            return list(value)
        except TypeError:
            pass
    # 标量 wrap 为单元素集合，对齐 Java Collections.singletonList。
    return [value]


def _loose_equal(a: Any, b: Any) -> bool:
    """Loose equality used by `in` / `not in`.

    对齐 Java `IN.looseEquals`：
    - None 仅等于 None
    - 两侧都是 Number（且都不是 bool）时按 Decimal 值比较
    - bool 与 Number 的跨类比较判为不等（Python 特有护栏，Java 无此陷阱）
    - 其他走 Python `==`
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    a_is_bool = isinstance(a, bool)
    b_is_bool = isinstance(b, bool)
    a_is_num = isinstance(a, (int, float, Decimal)) and not a_is_bool
    b_is_num = isinstance(b, (int, float, Decimal)) and not b_is_bool

    # bool 与 Number 跨类比较：强制不等（Python `True == 1` 会误判）
    if a_is_bool and b_is_num:
        return False
    if b_is_bool and a_is_num:
        return False

    # Number 之间：Decimal 值比较，打平 int / float / Decimal 类型差异
    if a_is_num and b_is_num:
        try:
            da = a if isinstance(a, Decimal) else Decimal(str(a))
            db = b if isinstance(b, Decimal) else Decimal(str(b))
            return da == db
        except (InvalidOperation, ValueError):
            return a == b

    try:
        return a == b
    except Exception:
        return False


def _check_in(left: Any, right: Any) -> bool:
    """`left in right` membership test.

    对齐 Java `IN.containsMember`：
    - right 为 None          -> False
    - right 展开为 haystack 后逐项 `_loose_equal(left, item)`
    - 任一命中返回 True；否则 False
    """
    haystack = _to_haystack(right)
    if haystack is None:
        return False
    # str haystack：使用 Python 原生子串语义（包含 startswith/substring）。
    # 只在左值是 str 时走子串；否则走逐字符 loose_equal（防止 "a" in "abc" 的
    # 元素各自去做 Number 归一）。
    if isinstance(haystack, str):
        if isinstance(left, str):
            return left in haystack
        # 非字符串左值与字符串 haystack：逐字符 loose 对比
        for ch in haystack:
            if _loose_equal(left, ch):
                return True
        return False
    for item in haystack:
        if _loose_equal(left, item):
            return True
    return False


__all__ = [
    "BinaryOperator",
    "UnaryOperator",
    "BinaryExpression",
    "UnaryExpression",
    "TernaryExpression",
    "UpdateOperator",
    "UpdateExpression",
    "fsscript_typeof",
]