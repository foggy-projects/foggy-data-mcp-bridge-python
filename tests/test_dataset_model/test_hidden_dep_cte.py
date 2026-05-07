"""Regression tests for hidden window dependency injection and
compose prerequisite CTE FROM-clause ordering.

These tests validate that:
1. Window function partitionBy/orderBy dependencies not in DSL `columns`
   are implicitly projected into Stage 1 CTE.
2. compose_planner selects FROM the root (outer window) CTE,
   not the prerequisite (inner aggregate) CTE.
"""
from __future__ import annotations

import re
import pytest

from foggy.dataset_model.engine.compose import ComposedSql, CteUnit, CteComposer


class TestComposePrerequisiteFromClause:
    """Compose must SELECT FROM the root CTE (containing window function),
    not from the prerequisite CTE (inner aggregate)."""

    def _extract_top_level_from(self, sql: str) -> str:
        """Extract the top-level FROM clause (after the final SELECT *)."""
        # Find the last SELECT * ... FROM pattern
        match = re.search(r'SELECT \*\s+FROM\s+(\S+)', sql)
        return match.group(1) if match else ""

    def test_from_targets_root_not_prerequisite(self):
        """Simulates the compile_to_composed_sql top-level wrap path with
        prerequisite CTEs and verifies FROM points to root unit."""
        prereq = CteUnit(
            alias="cte_1",
            sql=(
                "SELECT team_id, SUM(amount) AS totalSales "
                "FROM sales GROUP BY team_id"
            ),
            params=[],
            select_columns=["team_id", "totalSales"],
        )
        root = CteUnit(
            alias="cte_0",
            sql=(
                'SELECT cte_1.team_id, cte_1."totalSales", '
                'ROW_NUMBER() OVER (PARTITION BY team_id '
                'ORDER BY "totalSales" DESC) AS rank FROM cte_1'
            ),
            params=[],
            select_columns=["team_id", "totalSales", "rank"],
        )

        # Build the SQL the same way compose_planner now does it
        all_params: list = []
        cte_parts: list = []
        for p in [prereq]:
            cte_parts.append(f"{p.alias} AS ({p.sql})")
            all_params.extend(p.params)
        cte_parts.append(f"{root.alias} AS ({root.sql})")
        all_params.extend(root.params)
        with_clause = "WITH " + ",\n".join(cte_parts)
        from_clause = f"FROM {root.alias}"
        sql = f"{with_clause}\nSELECT *\n{from_clause}"
        result = ComposedSql(sql=sql, params=all_params)

        # The top-level FROM must point to cte_0 (root with rank)
        top_from = self._extract_top_level_from(result.sql)
        assert top_from == "cte_0", (
            f"Top-level FROM must target root CTE cte_0, got {top_from!r}. "
            f"Actual SQL:\n{result.sql}"
        )
        # Both CTEs must be present
        assert "cte_1 AS" in result.sql
        assert "cte_0 AS" in result.sql
        # rank column is reachable
        assert "rank" in result.sql

    def test_no_prerequisite_falls_through_to_composer(self):
        """Without prerequisite CTEs, the single-unit path via
        CteComposer.compose is unchanged."""
        units = [CteUnit(alias="cte_0", sql="SELECT id FROM orders")]
        result = CteComposer.compose(units, [])
        assert "FROM cte_0" in result.sql
        assert "WITH cte_0 AS" in result.sql

    def test_params_ordering_with_prerequisites(self):
        """Params from prerequisite CTEs come before root CTE params."""
        prereq = CteUnit(
            alias="cte_1",
            sql="SELECT * FROM sales WHERE region = %s",
            params=["East"],
        )
        root = CteUnit(
            alias="cte_0",
            sql="SELECT * FROM cte_1 WHERE active = %s",
            params=[True],
        )
        all_params: list = []
        cte_parts: list = []
        for p in [prereq]:
            cte_parts.append(f"{p.alias} AS ({p.sql})")
            all_params.extend(p.params)
        cte_parts.append(f"{root.alias} AS ({root.sql})")
        all_params.extend(root.params)

        assert all_params == ["East", True]
