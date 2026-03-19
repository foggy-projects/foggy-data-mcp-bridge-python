"""Base expression class for FSScript AST.

All expression types inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Expression(ABC, BaseModel):
    """Base class for all FSScript expressions.

    Expressions form an Abstract Syntax Tree (AST) that can be
    evaluated to produce a value.
    """

    # Source location for error reporting
    line: Optional[int] = Field(default=None, description="Source line number")
    column: Optional[int] = Field(default=None, description="Source column number")

    # Parent expression (for tree traversal)
    _parent: Optional["Expression"] = None

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate this expression in the given context.

        Args:
            context: Evaluation context with variables and functions

        Returns:
            Evaluation result
        """
        pass

    @abstractmethod
    def accept(self, visitor: "ExpressionVisitor") -> Any:
        """Accept a visitor (Visitor pattern).

        Args:
            visitor: Expression visitor

        Returns:
            Visitor result
        """
        pass

    @property
    def parent(self) -> Optional["Expression"]:
        """Get parent expression."""
        return self._parent

    @parent.setter
    def parent(self, value: Optional["Expression"]) -> None:
        """Set parent expression."""
        self._parent = value

    def get_source_location(self) -> str:
        """Get source location string for error messages.

        Returns:
            Source location string like "line:col" or "unknown"
        """
        if self.line is not None and self.column is not None:
            return f"{self.line}:{self.column}"
        return "unknown"


class ExpressionVisitor(ABC):
    """Abstract visitor for expression trees.

    Implements the Visitor pattern for traversing and processing
    expression trees.
    """

    @abstractmethod
    def visit_literal(self, expr: "LiteralExpression") -> Any:
        """Visit a literal expression."""
        pass

    @abstractmethod
    def visit_binary(self, expr: "BinaryExpression") -> Any:
        """Visit a binary expression."""
        pass

    @abstractmethod
    def visit_unary(self, expr: "UnaryExpression") -> Any:
        """Visit a unary expression."""
        pass

    @abstractmethod
    def visit_variable(self, expr: "VariableExpression") -> Any:
        """Visit a variable expression."""
        pass

    @abstractmethod
    def visit_function_call(self, expr: "FunctionCallExpression") -> Any:
        """Visit a function call expression."""
        pass

    @abstractmethod
    def visit_block(self, expr: "BlockExpression") -> Any:
        """Visit a block expression."""
        pass

    @abstractmethod
    def visit_if(self, expr: "IfExpression") -> Any:
        """Visit an if expression."""
        pass

    @abstractmethod
    def visit_for(self, expr: "ForExpression") -> Any:
        """Visit a for expression."""
        pass

    @abstractmethod
    def visit_while(self, expr: "WhileExpression") -> Any:
        """Visit a while expression."""
        pass

    @abstractmethod
    def visit_spread(self, expr: "SpreadExpression") -> Any:
        """Visit a spread expression."""
        pass

    @abstractmethod
    def visit_update(self, expr: "UpdateExpression") -> Any:
        """Visit an update expression (increment/decrement)."""
        pass

    @abstractmethod
    def visit_export(self, expr: "ExportExpression") -> Any:
        """Visit an export expression."""
        pass

    @abstractmethod
    def visit_import(self, expr: "ImportExpression") -> Any:
        """Visit an import expression."""
        pass

    @abstractmethod
    def visit_switch(self, expr: "SwitchExpression") -> Any:
        """Visit a switch expression."""
        pass


# Import these at module level to avoid circular imports
# They will be imported after the classes are defined
__all__ = [
    "Expression",
    "ExpressionVisitor",
]