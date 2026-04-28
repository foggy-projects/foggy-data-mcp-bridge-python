"""SQL-specific predicate AST nodes for the fsscript → SQL compilation path.

These nodes represent SQL constructs that don't exist in the fsscript
runtime (``IS NULL``, ``BETWEEN``, ``LIKE``, ``CAST``).  They are produced
by the parser when SQL-mode keywords are encountered in expression
position and are consumed exclusively by
:class:`~foggy.dataset_model.semantic.fsscript_to_sql_visitor.FsscriptToSqlVisitor`.

``evaluate()`` raises ``NotImplementedError`` — these nodes are never
executed in the fsscript interpreter; they exist only as intermediate
AST for SQL generation.

Stage 6 / Phase 4 — post-v1.5 follow-up.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field

from foggy.fsscript.expressions.base import Expression, ExpressionVisitor


class IsNullExpression(Expression):
    """``expr IS NULL`` / ``expr IS NOT NULL``."""

    operand: Expression = Field(..., description="Expression to test for NULL")
    negated: bool = Field(default=False, description="True for IS NOT NULL")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("IsNullExpression is SQL-only; use the SQL visitor")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        return visitor.visit(self)

    def __repr__(self) -> str:
        op = "IS NOT NULL" if self.negated else "IS NULL"
        return f"({self.operand} {op})"


class BetweenExpression(Expression):
    """``expr BETWEEN low AND high`` / ``expr NOT BETWEEN low AND high``."""

    operand: Expression = Field(..., description="Expression to test")
    low: Expression = Field(..., description="Lower bound")
    high: Expression = Field(..., description="Upper bound")
    negated: bool = Field(default=False, description="True for NOT BETWEEN")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("BetweenExpression is SQL-only; use the SQL visitor")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        return visitor.visit(self)

    def __repr__(self) -> str:
        op = "NOT BETWEEN" if self.negated else "BETWEEN"
        return f"({self.operand} {op} {self.low} AND {self.high})"


class LikeExpression(Expression):
    """``expr LIKE pattern`` / ``expr NOT LIKE pattern``."""

    operand: Expression = Field(..., description="Expression to match")
    pattern: Expression = Field(..., description="LIKE pattern")
    negated: bool = Field(default=False, description="True for NOT LIKE")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("LikeExpression is SQL-only; use the SQL visitor")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        return visitor.visit(self)

    def __repr__(self) -> str:
        op = "NOT LIKE" if self.negated else "LIKE"
        return f"({self.operand} {op} {self.pattern})"


class CastExpression(Expression):
    """``CAST(expr AS type_name)``."""

    operand: Expression = Field(..., description="Expression to cast")
    type_name: str = Field(..., description="SQL type name, e.g. 'INTEGER', 'VARCHAR(100)'")

    def evaluate(self, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("CastExpression is SQL-only; use the SQL visitor")

    def accept(self, visitor: ExpressionVisitor) -> Any:
        return visitor.visit(self)

    def __repr__(self) -> str:
        return f"CAST({self.operand} AS {self.type_name})"


__all__ = [
    "IsNullExpression",
    "BetweenExpression",
    "LikeExpression",
    "CastExpression",
]
