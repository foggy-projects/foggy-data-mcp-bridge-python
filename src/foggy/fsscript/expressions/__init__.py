"""Expressions package for FSScript AST."""

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor
from foggy.fsscript.expressions.literals import (
    LiteralExpression,
    NullExpression,
    BooleanExpression,
    NumberExpression,
    StringExpression,
    ArrayExpression,
    ObjectExpression,
)
from foggy.fsscript.expressions.operators import (
    BinaryOperator,
    UnaryOperator,
    BinaryExpression,
    UnaryExpression,
    TernaryExpression,
)
from foggy.fsscript.expressions.variables import (
    VariableExpression,
    MemberAccessExpression,
    IndexAccessExpression,
    AssignmentExpression,
)
from foggy.fsscript.expressions.functions import (
    FunctionCallExpression,
    MethodCallExpression,
    FunctionDefinitionExpression,
)
from foggy.fsscript.expressions.control_flow import (
    BlockExpression,
    IfExpression,
    ForExpression,
    WhileExpression,
    BreakExpression,
    ContinueExpression,
    ReturnExpression,
    BreakException,
    ContinueException,
    ReturnException,
)

__all__ = [
    # Base
    "Expression",
    "ExpressionVisitor",
    # Literals
    "LiteralExpression",
    "NullExpression",
    "BooleanExpression",
    "NumberExpression",
    "StringExpression",
    "ArrayExpression",
    "ObjectExpression",
    # Operators
    "BinaryOperator",
    "UnaryOperator",
    "BinaryExpression",
    "UnaryExpression",
    "TernaryExpression",
    # Variables
    "VariableExpression",
    "MemberAccessExpression",
    "IndexAccessExpression",
    "AssignmentExpression",
    # Functions
    "FunctionCallExpression",
    "MethodCallExpression",
    "FunctionDefinitionExpression",
    # Control flow
    "BlockExpression",
    "IfExpression",
    "ForExpression",
    "WhileExpression",
    "BreakExpression",
    "ContinueExpression",
    "ReturnExpression",
    "BreakException",
    "ContinueException",
    "ReturnException",
]