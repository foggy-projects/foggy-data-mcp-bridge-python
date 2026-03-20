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
    is_declaration: bool = Field(default=False, description="True for var/let/const declarations")
    is_block_scoped: bool = Field(default=False, description="True for let/const (not var)")


    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Assign value and return it."""
        val = self.value.evaluate(context)

        if isinstance(self.target, VariableExpression):
            if self.is_declaration:
                # var/let/const: declare in local scope (shadow outer vars)
                from foggy.fsscript.scope import ScopeChain
                if isinstance(context, ScopeChain):
                    context.declare(self.target.name, val)
                else:
                    context[self.target.name] = val
            else:
                # Plain assignment: update existing or create in local
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


class DestructuringExpression(Expression):
    """Destructuring assignment with defaults.

    Mirrors Java's ``DestructurePatternExp``.  Evaluates the source
    expression, then for each item extracts the named property from the
    resulting dict (or uses the default value when the property is
    ``None`` / missing).

    Example::

        const { name = 'date', foreignKey = 'date_key' } = options;

    AST::

        DestructuringExpression(
            properties=[
                {"name": "name",       "alias": None, "default": StringExpression("date")},
                {"name": "foreignKey", "alias": None, "default": StringExpression("date_key")},
            ],
            source=VariableExpression("options"),
        )
    """

    properties: List[dict] = Field(
        ...,
        description=(
            'List of {"name": str, "alias": str|None, "default": Expression|None}'
        ),
    )
    source: Expression = Field(..., description="Source expression to destructure")
    is_declaration: bool = Field(default=True)
    is_block_scoped: bool = Field(default=False)

    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Extract properties from source into context."""
        src_val = self.source.evaluate(context)
        if not isinstance(src_val, dict):
            src_val = {}

        from foggy.fsscript.scope import ScopeChain

        for prop in self.properties:
            prop_name: str = prop["name"]
            alias: str = prop.get("alias") or prop_name
            default_expr: Optional[Expression] = prop.get("default")

            value = src_val.get(prop_name)

            # Apply default when value is None / missing (Java semantics)
            if value is None and default_expr is not None:
                value = default_expr.evaluate(context)

            if self.is_declaration and isinstance(context, ScopeChain):
                context.declare(alias, value)
            else:
                context[alias] = value

        return src_val

    def accept(self, visitor: ExpressionVisitor) -> Any:
        """Accept visitor — reuse assignment visitor."""
        return visitor.visit_assignment(self)

    def __repr__(self) -> str:
        names = ", ".join(p["name"] for p in self.properties)
        return f"const {{{names}}} = {self.source}"


__all__ = [
    "VariableExpression",
    "MemberAccessExpression",
    "IndexAccessExpression",
    "AssignmentExpression",
    "DestructuringExpression",
]