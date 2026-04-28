"""6.5 · dialect CTE-vs-subquery fallback + 4-dialect SQL snapshots.

Uses ``tests/integration/_sql_normalizer.py`` to canonicalise emitted
SQL before assertions, matching the spec §验收硬门槛 #4 directive.

4 dialects × 3 shapes (single / union / join / derived-chain) with
structural rather than byte-for-byte comparison — the r3 Q3 addition
specifies derived-chain snapshots too because that is the only path
where M6 self-templates ``SELECT ... FROM (<inner>) AS alias``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The integration _sql_normalizer is kept intentionally private
# (filename starts with _). We reach it via sys.path.
_REPO_TESTS = Path(__file__).resolve().parents[2]
_INTEGRATION_DIR = _REPO_TESTS / "integration"
if str(_INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_DIR))

from _sql_normalizer import to_canonical  # type: ignore  # noqa: E402

from foggy.dataset_model.engine.compose.compilation import (
    compile_plan_to_sql,
)
from foggy.dataset_model.engine.compose.compilation.compose_planner import (
    dialect_supports_cte,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.plan.plan import JoinOn


# ---------------------------------------------------------------------------
# dialect_supports_cte truth table
# ---------------------------------------------------------------------------


class TestDialectCapabilityTable:
    @pytest.mark.parametrize(
        "dialect",
        ["mysql8", "postgres", "postgresql", "mssql", "sqlserver", "sqlite"],
    )
    def test_cte_capable_dialects(self, dialect):
        assert dialect_supports_cte(dialect) is True

    @pytest.mark.parametrize("dialect", ["mysql", "mysql57"])
    def test_mysql_legacy_is_not_cte_capable(self, dialect):
        assert dialect_supports_cte(dialect) is False

    def test_case_insensitive(self):
        assert dialect_supports_cte("Postgres") is True
        assert dialect_supports_cte("MYSQL8") is True
        assert dialect_supports_cte("MySQL") is False


# ---------------------------------------------------------------------------
# Single-base snapshot — 4 dialects
# ---------------------------------------------------------------------------


class TestSingleBase4Dialects:
    @pytest.fixture
    def plan(self):
        return from_(
            model="FactSalesModel",
            columns=["orderStatus$caption", "salesAmount"],
        )

    def test_mysql57_subquery_form(self, svc, ctx, plan):
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql"
        )
        # MySQL 5.7 does not support CTE → subquery form
        assert "WITH " not in composed.sql
        assert "FROM (" in composed.sql
        assert "AS t0" in composed.sql

    def test_mysql8_cte_form(self, svc, ctx, plan):
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        # MySQL 8 supports CTE → WITH form
        assert "WITH " in composed.sql
        assert "cte_0 AS" in composed.sql

    def test_postgres_cte_form(self, svc, ctx, plan):
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="postgres"
        )
        assert "WITH " in composed.sql
        assert "cte_0 AS" in composed.sql

    def test_mssql_cte_form(self, svc, ctx, plan):
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mssql"
        )
        assert "WITH " in composed.sql

    def test_sqlite_cte_form(self, svc, ctx, plan):
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="sqlite"
        )
        assert "WITH " in composed.sql


# ---------------------------------------------------------------------------
# Union snapshot — 4 dialects (union SQL is dialect-neutral; ensure no drift)
# ---------------------------------------------------------------------------


class TestUnion4Dialects:
    @pytest.fixture
    def union_plan(self, base_sales, base_orders):
        return base_sales.union(base_orders, all=True)

    @pytest.mark.parametrize(
        "dialect",
        ["mysql", "mysql8", "postgres", "sqlite"],
    )
    def test_union_contains_union_all_keyword(self, svc, ctx, union_plan, dialect):
        composed = compile_plan_to_sql(
            union_plan, ctx, semantic_service=svc, dialect=dialect
        )
        assert "UNION ALL" in composed.sql


# ---------------------------------------------------------------------------
# Join snapshot — 4 dialects
# ---------------------------------------------------------------------------


class TestJoin4Dialects:
    @pytest.fixture
    def join_plan(self, base_sales, base_orders):
        on = [JoinOn(left="orderStatus", op="=", right="orderStatus")]
        return base_sales.join(base_orders, type="inner", on=on)

    @pytest.mark.parametrize(
        "dialect,use_cte",
        [
            ("mysql", False),
            ("mysql8", True),
            ("postgres", True),
            ("mssql", True),
            ("sqlite", True),
        ],
    )
    def test_join_dialect_vs_cte_mode(self, svc, ctx, join_plan, dialect, use_cte):
        composed = compile_plan_to_sql(
            join_plan, ctx, semantic_service=svc, dialect=dialect
        )
        assert "INNER JOIN" in composed.sql
        if use_cte:
            assert "WITH " in composed.sql
        else:
            assert "WITH " not in composed.sql


# ---------------------------------------------------------------------------
# r3 Q3 addition: 4-dialect × derived-chain snapshot
# ---------------------------------------------------------------------------


class TestDerivedChain4Dialects:
    """r3 Q3: derived chain is the ONLY path where M6 templates
    ``SELECT … FROM (<inner>) AS alias`` itself — snapshot it across
    4 dialects to catch dialect drift early."""

    @pytest.fixture
    def derived_chain_plan(self, base_sales):
        d1 = base_sales.query(columns=["orderStatus$caption"])
        d2 = d1.query(columns=["orderStatus$caption"])
        return d2

    def test_derived_chain_mysql57(self, svc, ctx, derived_chain_plan):
        composed = compile_plan_to_sql(
            derived_chain_plan, ctx, semantic_service=svc, dialect="mysql"
        )
        # At least 2 nested ``FROM (...) AS`` layers
        assert composed.sql.count("FROM (") >= 2
        # Outer SELECT ... not wrapped in WITH (MySQL 5.7 no CTE)
        assert not composed.sql.startswith("WITH ")

    def test_derived_chain_mysql8(self, svc, ctx, derived_chain_plan):
        composed = compile_plan_to_sql(
            derived_chain_plan, ctx, semantic_service=svc, dialect="mysql8"
        )
        assert composed.sql.count("FROM (") >= 2

    def test_derived_chain_postgres(self, svc, ctx, derived_chain_plan):
        composed = compile_plan_to_sql(
            derived_chain_plan, ctx, semantic_service=svc, dialect="postgres"
        )
        assert composed.sql.count("FROM (") >= 2

    def test_derived_chain_sqlite(self, svc, ctx, derived_chain_plan):
        composed = compile_plan_to_sql(
            derived_chain_plan, ctx, semantic_service=svc, dialect="sqlite"
        )
        assert composed.sql.count("FROM (") >= 2


# ---------------------------------------------------------------------------
# Param ordering preserved across dialects (regression guard)
# ---------------------------------------------------------------------------


class TestDialectParamOrdering:
    """Same plan, 4 dialects → params list is identical (dialect only
    affects SQL shape, not param values / order)."""

    @pytest.fixture
    def slice_plan(self, base_sales):
        return base_sales.query(
            columns=["orderStatus$caption"],
            slice=[{"field": "orderStatus", "op": "=", "value": "done"}],
        )

    def test_params_identical_across_dialects(self, svc, ctx, slice_plan):
        dialects = ["mysql", "mysql8", "postgres", "sqlite"]
        params_per_dialect = []
        for dialect in dialects:
            composed = compile_plan_to_sql(
                slice_plan, ctx, semantic_service=svc, dialect=dialect
            )
            params_per_dialect.append(tuple(composed.params))
        # All 4 dialects emit the same param tuple
        assert len(set(params_per_dialect)) == 1, (
            f"param drift across dialects: {params_per_dialect}"
        )
        # And the value is actually bound
        assert params_per_dialect[0] == ("done",)


# ---------------------------------------------------------------------------
# Unknown dialect → clear error
# ---------------------------------------------------------------------------


class TestUnknownDialect:
    def test_unknown_dialect_raises_unsupported(self, svc, ctx, base_sales):
        from foggy.dataset_model.engine.compose.compilation import (
            ComposeCompileError,
            error_codes,
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            compile_plan_to_sql(
                base_sales,
                ctx,
                semantic_service=svc,
                dialect="oracle",  # not in the registered set
            )
        assert exc_info.value.code == error_codes.UNSUPPORTED_PLAN_SHAPE
        assert "oracle" in exc_info.value.message.lower()
