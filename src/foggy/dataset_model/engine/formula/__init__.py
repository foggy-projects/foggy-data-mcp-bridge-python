"""SqlFormula system — operator-based SQL condition generation.

Aligned with Java engine/formula/ (SqlFormulaService + 15 operator classes).
Replaces ad-hoc if/elif chains with a registry pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

__all__ = [
    "SqlFormula",
    "SqlFormulaRegistry",
    "get_default_registry",
    # Operator implementations
    "EqFormula",
    "NotEqFormula",
    "GtFormula",
    "GteFormula",
    "LtFormula",
    "LteFormula",
    "InFormula",
    "NotInFormula",
    "LikeFormula",
    "LeftLikeFormula",
    "RightLikeFormula",
    "IsNullFormula",
    "IsNotNullFormula",
    "RangeFormula",
    "BetweenFormula",
]


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class SqlFormula(ABC):
    """Abstract base for SQL condition generators."""

    @abstractmethod
    def build_condition(
        self,
        column_expr: str,
        op: str,
        value: Any,
        params: list,
    ) -> str:
        """Return a SQL fragment and append bind-values to *params*.

        Parameters
        ----------
        column_expr:
            Fully-qualified column expression (e.g. ``"dp.name"``).
        op:
            The operator name as written by the caller (useful when a single
            formula class handles multiple aliases like ``!=`` / ``<>``).
        value:
            The operand value.  Type depends on the operator — may be a scalar,
            list, dict, or ``None``.
        params:
            Mutable list to which bind-parameter values are appended.

        Returns
        -------
        str
            SQL fragment such as ``"dp.name LIKE ?"`` or ``"dp.id IN (?, ?)"``
        """


# ---------------------------------------------------------------------------
# Simple comparison operators
# ---------------------------------------------------------------------------

class EqFormula(SqlFormula):
    """``=`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} = ?"


class NotEqFormula(SqlFormula):
    """``!=`` / ``<>`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} <> ?"


class GtFormula(SqlFormula):
    """``>`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} > ?"


class GteFormula(SqlFormula):
    """``>=`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} >= ?"


class LtFormula(SqlFormula):
    """``<`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} < ?"


class LteFormula(SqlFormula):
    """``<=`` operator."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(value)
        return f"{column_expr} <= ?"


# ---------------------------------------------------------------------------
# IN / NOT IN
# ---------------------------------------------------------------------------

class InFormula(SqlFormula):
    """``in`` operator — value must be a list."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        if not isinstance(value, (list, tuple)):
            value = [value]
        placeholders = ", ".join("?" for _ in value)
        params.extend(value)
        return f"{column_expr} IN ({placeholders})"


class NotInFormula(SqlFormula):
    """``not in`` / ``nin`` operator — value must be a list."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        if not isinstance(value, (list, tuple)):
            value = [value]
        placeholders = ", ".join("?" for _ in value)
        params.extend(value)
        return f"{column_expr} NOT IN ({placeholders})"


# ---------------------------------------------------------------------------
# LIKE variants
# ---------------------------------------------------------------------------

class LikeFormula(SqlFormula):
    """``like`` — wraps value with ``%`` on both sides."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(f"%{value}%")
        return f"{column_expr} LIKE ?"


class LeftLikeFormula(SqlFormula):
    """``left_like`` — appends ``%`` after value (prefix match)."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(f"{value}%")
        return f"{column_expr} LIKE ?"


class RightLikeFormula(SqlFormula):
    """``right_like`` — prepends ``%`` before value (suffix match)."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        params.append(f"%{value}")
        return f"{column_expr} LIKE ?"


# ---------------------------------------------------------------------------
# NULL checks
# ---------------------------------------------------------------------------

class IsNullFormula(SqlFormula):
    """``is null`` / ``isNull`` — no params appended."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        return f"{column_expr} IS NULL"


class IsNotNullFormula(SqlFormula):
    """``is not null`` / ``isNotNull`` — no params appended."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        return f"{column_expr} IS NOT NULL"


# ---------------------------------------------------------------------------
# Range / Between
# ---------------------------------------------------------------------------

class RangeFormula(SqlFormula):
    """Range operators: ``[]``, ``[)``, ``(]``, ``()``.

    Value must be a list/tuple of ``[start, end]``.

    * ``[`` = inclusive (``>=``)
    * ``(`` = exclusive (``>``)
    * ``]`` = inclusive (``<=``)
    * ``)`` = exclusive (``<``)
    """

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(
                f"Range operator '{op}' requires a [start, end] list, got: {value!r}"
            )

        start, end = value

        left_inclusive = op[0] == "["
        right_inclusive = op[-1] == "]"

        parts: list[str] = []

        if start is not None:
            cmp = ">=" if left_inclusive else ">"
            parts.append(f"{column_expr} {cmp} ?")
            params.append(start)

        if end is not None:
            cmp = "<=" if right_inclusive else "<"
            parts.append(f"{column_expr} {cmp} ?")
            params.append(end)

        if not parts:
            return "1 = 1"

        return " AND ".join(parts)


class BetweenFormula(SqlFormula):
    """``between`` — value must be a list/tuple of ``[start, end]``."""

    def build_condition(self, column_expr: str, op: str, value: Any, params: list) -> str:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(
                f"BETWEEN operator requires a [start, end] list, got: {value!r}"
            )
        start, end = value
        params.append(start)
        params.append(end)
        return f"{column_expr} BETWEEN ? AND ?"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SqlFormulaRegistry:
    """Operator-name to :class:`SqlFormula` registry."""

    def __init__(self) -> None:
        self._formulas: Dict[str, SqlFormula] = {}

    # -- registration -------------------------------------------------------

    def register(self, op_name: str, formula: SqlFormula) -> None:
        """Register *formula* for *op_name* (case-sensitive)."""
        self._formulas[op_name] = formula

    # -- lookup & build -----------------------------------------------------

    def get(self, op_name: str) -> Optional[SqlFormula]:
        """Return the formula for *op_name*, or ``None``."""
        return self._formulas.get(op_name)

    def build_condition(
        self,
        column_expr: str,
        op: str,
        value: Any,
        params: list,
    ) -> str:
        """Delegate to the registered formula for *op*.

        Raises :class:`KeyError` if no formula is registered.
        """
        formula = self._formulas.get(op)
        if formula is None:
            raise KeyError(f"Unknown operator: {op!r}")
        return formula.build_condition(column_expr, op, value, params)

    @property
    def operators(self) -> list[str]:
        """Return a sorted list of registered operator names."""
        return sorted(self._formulas)

    def __contains__(self, op_name: str) -> bool:
        return op_name in self._formulas

    def __len__(self) -> int:
        return len(self._formulas)


# ---------------------------------------------------------------------------
# Default registry factory
# ---------------------------------------------------------------------------

def get_default_registry() -> SqlFormulaRegistry:
    """Create a :class:`SqlFormulaRegistry` pre-loaded with all built-in operators."""
    reg = SqlFormulaRegistry()

    # simple comparison
    reg.register("=", EqFormula())
    reg.register("eq", EqFormula())

    reg.register("!=", NotEqFormula())
    reg.register("<>", NotEqFormula())
    reg.register("neq", NotEqFormula())

    reg.register(">", GtFormula())
    reg.register("gt", GtFormula())

    reg.register(">=", GteFormula())
    reg.register("gte", GteFormula())

    reg.register("<", LtFormula())
    reg.register("lt", LtFormula())

    reg.register("<=", LteFormula())
    reg.register("lte", LteFormula())

    # in / not in
    reg.register("in", InFormula())
    reg.register("not in", NotInFormula())
    reg.register("nin", NotInFormula())

    # like variants
    reg.register("like", LikeFormula())
    reg.register("left_like", LeftLikeFormula())
    reg.register("right_like", RightLikeFormula())

    # null checks
    reg.register("is null", IsNullFormula())
    reg.register("isNull", IsNullFormula())
    reg.register("is not null", IsNotNullFormula())
    reg.register("isNotNull", IsNotNullFormula())

    # range / between
    range_formula = RangeFormula()
    reg.register("[]", range_formula)
    reg.register("[)", range_formula)
    reg.register("(]", range_formula)
    reg.register("()", range_formula)

    reg.register("between", BetweenFormula())

    return reg
