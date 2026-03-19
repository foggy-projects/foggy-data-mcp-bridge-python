"""SQL expression classes for semantic layer engine."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel


class SqlOperator(str, Enum):
    """SQL operator enumeration."""

    # Comparison
    EQ = "="
    NE = "<>"
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="

    # Logical
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # Arithmetic
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"

    # Set
    IN = "IN"
    NOT_IN = "NOT IN"
    EXISTS = "EXISTS"

    # Pattern
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    BETWEEN = "BETWEEN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class SqlExp(ABC, BaseModel):
    """Base class for SQL expressions.

    Abstract base for all SQL expression types including
    literals, columns, binary operations, and functions.
    """

    @abstractmethod
    def to_sql(self) -> str:
        """Convert expression to SQL string.

        Returns:
            SQL expression string
        """
        pass

    def __str__(self) -> str:
        """String representation."""
        return self.to_sql()

    def and_(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create AND expression.

        Args:
            other: Right operand

        Returns:
            Binary AND expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.AND, right=other)

    def or_(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create OR expression.

        Args:
            other: Right operand

        Returns:
            Binary OR expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.OR, right=other)

    def eq(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create equality expression.

        Args:
            other: Right operand

        Returns:
            Binary equality expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.EQ, right=other)

    def ne(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create not-equal expression.

        Args:
            other: Right operand

        Returns:
            Binary not-equal expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.NE, right=other)

    def gt(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create greater-than expression.

        Args:
            other: Right operand

        Returns:
            Binary greater-than expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.GT, right=other)

    def ge(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create greater-or-equal expression.

        Args:
            other: Right operand

        Returns:
            Binary >= expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.GE, right=other)

    def lt(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create less-than expression.

        Args:
            other: Right operand

        Returns:
            Binary < expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.LT, right=other)

    def le(self, other: "SqlExp") -> "SqlBinaryExp":
        """Create less-or-equal expression.

        Args:
            other: Right operand

        Returns:
            Binary <= expression
        """
        return SqlBinaryExp(left=self, operator=SqlOperator.LE, right=other)

    def not_(self) -> "SqlUnaryExp":
        """Create NOT expression.

        Returns:
            Unary NOT expression
        """
        return SqlUnaryExp(operator=SqlOperator.NOT, operand=self)

    def in_(self, values: List[Any]) -> "SqlInExp":
        """Create IN expression.

        Args:
            values: List of values

        Returns:
            IN expression
        """
        return SqlInExp(column=self, values=values, negated=False)

    def not_in(self, values: List[Any]) -> "SqlInExp":
        """Create NOT IN expression.

        Args:
            values: List of values

        Returns:
            NOT IN expression
        """
        return SqlInExp(column=self, values=values, negated=True)

    def like(self, pattern: str) -> "SqlBinaryExp":
        """Create LIKE expression.

        Args:
            pattern: LIKE pattern

        Returns:
            LIKE expression
        """
        return SqlBinaryExp(
            left=self,
            operator=SqlOperator.LIKE,
            right=SqlLiteralExp(value=pattern)
        )

    def is_null(self) -> "SqlUnaryExp":
        """Create IS NULL expression.

        Returns:
            IS NULL expression
        """
        return SqlUnaryExp(operator=SqlOperator.IS_NULL, operand=self)

    def is_not_null(self) -> "SqlUnaryExp":
        """Create IS NOT NULL expression.

        Returns:
            IS NOT NULL expression
        """
        return SqlUnaryExp(operator=SqlOperator.IS_NOT_NULL, operand=self)


class SqlLiteralExp(SqlExp):
    """Literal value expression.

    Represents a literal value in SQL expressions.
    """

    value: Any

    def to_sql(self) -> str:
        """Convert to SQL literal.

        Returns:
            SQL literal string
        """
        if self.value is None:
            return "NULL"
        elif isinstance(self.value, bool):
            return "TRUE" if self.value else "FALSE"
        elif isinstance(self.value, str):
            # Escape single quotes
            escaped = self.value.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(self.value, (int, float)):
            return str(self.value)
        else:
            return f"'{self.value}'"


class SqlColumnExp(SqlExp):
    """Column reference expression.

    Represents a column reference in SQL expressions.
    """

    name: str
    table: Optional[str] = None
    alias: Optional[str] = None

    def to_sql(self) -> str:
        """Convert to SQL column reference.

        Returns:
            SQL column reference
        """
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name


class SqlBinaryExp(SqlExp):
    """Binary operation expression.

    Represents a binary operation (e.g., a + b, a = b, a AND b).
    """

    left: SqlExp
    operator: SqlOperator
    right: SqlExp

    def to_sql(self) -> str:
        """Convert to SQL binary expression.

        Returns:
            SQL binary expression
        """
        left_sql = self.left.to_sql()
        right_sql = self.right.to_sql()

        if self.operator in (SqlOperator.AND, SqlOperator.OR):
            return f"({left_sql} {self.operator.value} {right_sql})"

        return f"{left_sql} {self.operator.value} {right_sql}"


class SqlUnaryExp(SqlExp):
    """Unary operation expression.

    Represents a unary operation (e.g., NOT a, -a, IS NULL).
    """

    operator: SqlOperator
    operand: SqlExp

    def to_sql(self) -> str:
        """Convert to SQL unary expression.

        Returns:
            SQL unary expression
        """
        operand_sql = self.operand.to_sql()

        if self.operator == SqlOperator.NOT:
            return f"NOT {operand_sql}"
        elif self.operator == SqlOperator.IS_NULL:
            return f"{operand_sql} IS NULL"
        elif self.operator == SqlOperator.IS_NOT_NULL:
            return f"{operand_sql} IS NOT NULL"
        elif self.operator == SqlOperator.SUB:
            return f"-{operand_sql}"

        return f"{self.operator.value} {operand_sql}"


class SqlInExp(SqlExp):
    """IN expression.

    Represents an IN or NOT IN expression.
    """

    column: SqlExp
    values: List[Any]
    negated: bool = False

    def to_sql(self) -> str:
        """Convert to SQL IN expression.

        Returns:
            SQL IN expression
        """
        values_sql = ", ".join(
            SqlLiteralExp(value=v).to_sql() for v in self.values
        )
        keyword = "NOT IN" if self.negated else "IN"
        return f"{self.column.to_sql()} {keyword} ({values_sql})"


class SqlBetweenExp(SqlExp):
    """BETWEEN expression.

    Represents a BETWEEN expression for range conditions.
    """

    column: SqlExp
    from_value: Any
    to_value: Any
    negated: bool = False

    def to_sql(self) -> str:
        """Convert to SQL BETWEEN expression.

        Returns:
            SQL BETWEEN expression
        """
        from_sql = SqlLiteralExp(value=self.from_value).to_sql()
        to_sql = SqlLiteralExp(value=self.to_value).to_sql()

        if self.negated:
            return f"{self.column.to_sql()} NOT BETWEEN {from_sql} AND {to_sql}"
        return f"{self.column.to_sql()} BETWEEN {from_sql} AND {to_sql}"


class SqlFunctionExp(SqlExp):
    """SQL function expression.

    Represents a SQL function call (e.g., SUM, COUNT, MAX).
    """

    name: str
    args: List[SqlExp] = []
    distinct: bool = False

    def to_sql(self) -> str:
        """Convert to SQL function call.

        Returns:
            SQL function expression
        """
        args_sql = ", ".join(arg.to_sql() for arg in self.args)

        if self.distinct and len(self.args) == 1:
            return f"{self.name}(DISTINCT {args_sql})"

        return f"{self.name}({args_sql})"


class SqlCaseExp(SqlExp):
    """CASE expression.

    Represents a SQL CASE WHEN expression.
    """

    cases: List[tuple] = []  # List of (condition, result) tuples
    else_result: Optional[SqlExp] = None

    def to_sql(self) -> str:
        """Convert to SQL CASE expression.

        Returns:
            SQL CASE expression
        """
        parts = ["CASE"]

        for condition, result in self.cases:
            cond_sql = condition.to_sql() if isinstance(condition, SqlExp) else str(condition)
            result_sql = result.to_sql() if isinstance(result, SqlExp) else str(result)
            parts.append(f" WHEN {cond_sql} THEN {result_sql}")

        if self.else_result:
            else_sql = self.else_result.to_sql() if isinstance(self.else_result, SqlExp) else str(self.else_result)
            parts.append(f" ELSE {else_sql}")

        parts.append(" END")
        return "".join(parts)


# Factory functions for convenience
def col(name: str, table: Optional[str] = None) -> SqlColumnExp:
    """Create a column expression.

    Args:
        name: Column name
        table: Optional table name

    Returns:
        Column expression
    """
    return SqlColumnExp(name=name, table=table)


def lit(value: Any) -> SqlLiteralExp:
    """Create a literal expression.

    Args:
        value: Literal value

    Returns:
        Literal expression
    """
    return SqlLiteralExp(value=value)


def and_(*expressions: SqlExp) -> SqlExp:
    """Create AND expression from multiple expressions.

    Args:
        expressions: Expressions to AND together

    Returns:
        AND expression
    """
    if len(expressions) == 0:
        return SqlLiteralExp(value=True)
    if len(expressions) == 1:
        return expressions[0]

    result = expressions[0]
    for exp in expressions[1:]:
        result = result.and_(exp)
    return result


def or_(*expressions: SqlExp) -> SqlExp:
    """Create OR expression from multiple expressions.

    Args:
        expressions: Expressions to OR together

    Returns:
        OR expression
    """
    if len(expressions) == 0:
        return SqlLiteralExp(value=False)
    if len(expressions) == 1:
        return expressions[0]

    result = expressions[0]
    for exp in expressions[1:]:
        result = result.or_(exp)
    return result