"""CTE Composer — simple string-based CTE / subquery assembly.

Aligned with Java ``CteComposer``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CteUnit:
    """One logical query block that becomes a CTE or inline subquery."""

    alias: str  # e.g., "cte_0"
    sql: str  # The subquery SQL
    params: List[Any] = field(default_factory=list)
    select_columns: Optional[List[str]] = None  # Column projection


@dataclass
class JoinSpec:
    """Describes how two CTE units are joined."""

    left_alias: str
    right_alias: str
    on_condition: str  # e.g., "cte_0.order_id = cte_1.order_id"
    join_type: str = "LEFT"


@dataclass
class ComposedSql:
    """The final assembled SQL with merged parameters."""

    sql: str
    params: List[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------

class CteComposer:
    """Composes multiple SQL queries into a single CTE or subquery statement."""

    @staticmethod
    def compose(
        units: List[CteUnit],
        join_specs: List[JoinSpec],
        use_cte: bool = True,
        select_columns: Optional[List[str]] = None,
    ) -> ComposedSql:
        """Compose multiple query units into a single SQL statement.

        **CTE mode** (``use_cte=True``)::

            WITH cte_0 AS (SELECT ...), cte_1 AS (SELECT ...)
            SELECT ... FROM cte_0 LEFT JOIN cte_1 ON ...

        **Subquery mode** (``use_cte=False``)::

            SELECT ... FROM (SELECT ...) AS t0 LEFT JOIN (SELECT ...) AS t1 ON ...

        Args:
            units: Query units to compose.
            join_specs: Join specifications between units.
            use_cte: Use CTE (WITH) syntax when ``True``; inline subqueries
                     when ``False``.
            select_columns: Explicit column list for the outer SELECT.
                            Defaults to ``SELECT *``.

        Returns:
            A :class:`ComposedSql` containing the assembled SQL and merged
            parameter list.
        """
        if not units:
            return ComposedSql(sql="SELECT 1", params=[])

        all_params: List[Any] = []

        # SELECT clause
        if select_columns:
            select_clause = "SELECT " + ", ".join(select_columns)
        else:
            select_clause = "SELECT *"

        if use_cte:
            return CteComposer._compose_cte(
                units, join_specs, select_clause, all_params,
            )
        else:
            return CteComposer._compose_subquery(
                units, join_specs, select_clause, all_params,
            )

    # ------------------------------------------------------------------
    # CTE mode
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_cte(
        units: List[CteUnit],
        join_specs: List[JoinSpec],
        select_clause: str,
        all_params: List[Any],
    ) -> ComposedSql:
        cte_parts: List[str] = []
        for unit in units:
            cte_parts.append(f"{unit.alias} AS ({unit.sql})")
            all_params.extend(unit.params)

        with_clause = "WITH " + ",\n".join(cte_parts)
        from_clause = f"FROM {units[0].alias}"

        join_clauses: List[str] = []
        for spec in join_specs:
            join_clauses.append(
                f"{spec.join_type} JOIN {spec.right_alias} ON {spec.on_condition}"
            )

        parts = [with_clause, select_clause, from_clause]
        if join_clauses:
            parts.extend(join_clauses)

        sql = "\n".join(parts)
        return ComposedSql(sql=sql, params=all_params)

    # ------------------------------------------------------------------
    # Subquery mode
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_subquery(
        units: List[CteUnit],
        join_specs: List[JoinSpec],
        select_clause: str,
        all_params: List[Any],
    ) -> ComposedSql:
        # Build alias mapping: original alias -> subquery alias (t0, t1, ...)
        alias_map = {}
        for idx, unit in enumerate(units):
            alias_map[unit.alias] = f"t{idx}"

        # First unit as FROM
        first = units[0]
        all_params.extend(first.params)
        from_clause = f"FROM ({first.sql}) AS {alias_map[first.alias]}"

        join_clauses: List[str] = []
        for spec in join_specs:
            # Find the unit for the right side to get its SQL/params
            right_unit = next((u for u in units if u.alias == spec.right_alias), None)
            if right_unit is None:
                continue
            all_params.extend(right_unit.params)
            right_sub_alias = alias_map[right_unit.alias]

            # Rewrite ON condition: replace original aliases with subquery aliases
            on_cond = spec.on_condition
            for orig, sub in alias_map.items():
                on_cond = on_cond.replace(f"{orig}.", f"{sub}.")

            join_clauses.append(
                f"{spec.join_type} JOIN ({right_unit.sql}) AS {right_sub_alias} "
                f"ON {on_cond}"
            )

        # Rewrite select clause aliases too
        rewritten_select = select_clause
        for orig, sub in alias_map.items():
            rewritten_select = rewritten_select.replace(f"{orig}.", f"{sub}.")

        parts = [rewritten_select, from_clause]
        if join_clauses:
            parts.extend(join_clauses)

        sql = "\n".join(parts)
        return ComposedSql(sql=sql, params=all_params)
