"""Literal expression types."""

from typing import Any, Dict, Optional, Union
from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class LiteralExpression(Expression):
    """Literal value expression (numbers, strings, booleans, null)."""

    value: Any = Field(..., description="Literal value")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Return the literal value."""
        return self.value

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_literal(self)

    def __repr__(self) -> str:
        """String representation."""
        return f"Literal({self.value!r})"


class NullExpression(LiteralExpression):
    """Null literal expression."""

    value: None = None

    def __init__(self, **data):
        super().__init__(value=None, **data)

    def __repr__(self) -> str:
        return "Null"


class BooleanExpression(LiteralExpression):
    """Boolean literal expression."""

    value: bool

    def __init__(self, value: bool, **data):
        super().__init__(value=value, **data)

    def __repr__(self) -> str:
        return "True" if self.value else "False"


class NumberExpression(LiteralExpression):
    """Numeric literal expression."""

    value: Union[int, float]

    def __init__(self, value: Union[int, float], **data):
        super().__init__(value=value, **data)

    def __repr__(self) -> str:
        return f"Number({self.value})"


class StringExpression(LiteralExpression):
    """String literal expression."""

    value: str

    def __init__(self, value: str, **data):
        super().__init__(value=value, **data)

    def __repr__(self) -> str:
        return f"String({self.value!r})"


class SpreadExpression(Expression):
    """Spread operator expression (...expr)."""

    expression: Expression = Field(..., description="Expression to spread")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate and return the spreadable value."""
        return self.expression.evaluate(context)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_spread(self)

    def __repr__(self) -> str:
        return f"...{self.expression}"


class ArrayExpression(Expression):
    """Array literal expression."""

    elements: list[Expression] = Field(default_factory=list, description="Array elements")

    def evaluate(self, context: Dict[str, Any]) -> list:
        """Evaluate all elements and return array, expanding spread elements."""
        result = []
        for elem in self.elements:
            if isinstance(elem, SpreadExpression):
                spread_val = elem.evaluate(context)
                if isinstance(spread_val, list):
                    result.extend(spread_val)
                elif spread_val is not None:
                    result.append(spread_val)
            else:
                result.append(elem.evaluate(context))
        return result

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_array(self)

    def __repr__(self) -> str:
        return f"Array({len(self.elements)} elements)"


class ObjectExpression(Expression):
    """Object/dictionary literal expression."""

    properties: Dict[str, Expression] = Field(
        default_factory=dict, description="Object properties"
    )

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all properties and return object."""
        return {
            key: expr.evaluate(context)
            for key, expr in self.properties.items()
        }

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_object(self)

    def __repr__(self) -> str:
        return f"Object({len(self.properties)} properties)"


__all__ = [
    "LiteralExpression",
    "NullExpression",
    "BooleanExpression",
    "NumberExpression",
    "StringExpression",
    "ArrayExpression",
    "ObjectExpression",
    "SpreadExpression",
]