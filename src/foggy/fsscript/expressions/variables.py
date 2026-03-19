"""Variable and member access expressions."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class VariableExpression(Expression):
    """Variable reference expression."""

    name: str = Field(..., description="Variable name")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Look up the variable in context."""
        return context.get(self.name)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_variable(self)

    def __repr__(self) -> str:
        return f"Var({self.name})"


class MemberAccessExpression(Expression):
    """Member access expression (e.g., obj.property, arr[0])."""

    obj: Expression = Field(..., description="Object expression")
    member: str = Field(..., description="Member name")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Access member of object."""
        obj_val = self.obj.evaluate(context)

        if obj_val is None:
            return None

        if isinstance(obj_val, dict):
            return obj_val.get(self.member)
        elif isinstance(obj_val, list):
            # Handle length property
            if self.member == "length":
                return len(obj_val)
            try:
                index = int(self.member)
                if 0 <= index < len(obj_val):
                    return obj_val[index]
                return None
            except ValueError:
                return None
        elif isinstance(obj_val, str):
            # Handle length property for strings
            if self.member == "length":
                return len(obj_val)
            # Try attribute access
            return getattr(obj_val, self.member, None)
        else:
            # Try attribute access
            return getattr(obj_val, self.member, None)

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_member_access(self)

    def __repr__(self) -> str:
        return f"{self.obj}.{self.member}"


class IndexAccessExpression(Expression):
    """Index access expression (e.g., arr[index], map[key])."""

    obj: Expression = Field(..., description="Object expression")
    index: Expression = Field(..., description="Index expression")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Access by index."""
        obj_val = self.obj.evaluate(context)
        index_val = self.index.evaluate(context)

        if obj_val is None:
            return None

        if isinstance(obj_val, dict):
            if isinstance(index_val, str):
                return obj_val.get(index_val)
            return obj_val.get(str(index_val))

        elif isinstance(obj_val, list):
            if isinstance(index_val, (int, float)):
                idx = int(index_val)
                if -len(obj_val) <= idx < len(obj_val):
                    return obj_val[idx]
            return None

        elif isinstance(obj_val, str):
            if isinstance(index_val, (int, float)):
                idx = int(index_val)
                if 0 <= idx < len(obj_val):
                    return obj_val[idx]
            return None

        return None

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_index_access(self)

    def __repr__(self) -> str:
        return f"{self.obj}[{self.index}]"


class AssignmentExpression(Expression):
    """Assignment expression (e.g., x = value, obj.prop = value)."""

    target: Expression = Field(..., description="Target (variable or member)")
    value: Expression = Field(..., description="Value to assign")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Assign value and return it."""
        val = self.value.evaluate(context)

        if isinstance(self.target, VariableExpression):
            context[self.target.name] = val
        elif isinstance(self.target, MemberAccessExpression):
            obj_val = self.target.obj.evaluate(context)
            if isinstance(obj_val, dict):
                obj_val[self.target.member] = val
        elif isinstance(self.target, IndexAccessExpression):
            obj_val = self.target.obj.evaluate(context)
            index_val = self.target.index.evaluate(context)
            if isinstance(obj_val, dict):
                obj_val[str(index_val)] = val
            elif isinstance(obj_val, list) and isinstance(index_val, (int, float)):
                idx = int(index_val)
                if 0 <= idx < len(obj_val):
                    obj_val[idx] = val

        return val

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor."""
        return visitor.visit_assignment(self)

    def __repr__(self) -> str:
        return f"({self.target} = {self.value})"


__all__ = [
    "VariableExpression",
    "MemberAccessExpression",
    "IndexAccessExpression",
    "AssignmentExpression",
]