"""Operator expressions (binary and unary)."""

from enum import Enum
from typing import Any, Dict, Optional
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

        # Logical
        elif op == BinaryOperator.AND:
            return self._to_bool(left_val) and self._to_bool(right_val)
        elif op == BinaryOperator.OR:
            return self._to_bool(left_val) or self._to_bool(right_val)

        # String
        elif op == BinaryOperator.CONCAT:
            return self._to_string(left_val) + self._to_string(right_val)

        # Null-safe
        elif op == BinaryOperator.NULL_COALESCE:
            return right_val if left_val is None else left_val

        # Type check
        elif op == BinaryOperator.INSTANCEOF:
            return _check_instanceof(left_val, right_val)

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