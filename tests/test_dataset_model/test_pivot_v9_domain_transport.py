"""P3-B Stage 5A Domain Transport — renderer unit tests + SQLite oracle parity.

Key requirement: all oracle parity tests MUST execute the SQL produced by
``assemble_domain_transport_sql()`` directly — not hand-written SQL — so that
any bug in the assembler or renderer is caught.

Covers:
  - SqliteCteDomainRenderer fragment shape (CTE SQL, column defs, params order)
  - NULL-safe predicate builder (SQLite IS operator)
  - build_join_predicate: correct left-side expression from field_sql_map
  - assemble_domain_transport_sql: executable SQL (CTE + JOIN before GROUP BY)
  - Parameter limit fail-closed (> 999 refused)
  - Unsupported / None dialect fail-closed
  - SQLite oracle parity (additive SUM — assembled SQL vs hand-written oracle)
  - SQLite oracle parity (non-additive COUNT DISTINCT — proves pre-agg injection)
  - NULL domain member parity
  - Params ordering (domain params precede base params for CTE strategy)
"""

import sqlite3
import pytest

from foggy.dataset_model.semantic.pivot.domain_transport import (
    DomainTransportPlan,
    DomainRelationFragment,
    SqliteCteDomainRenderer,
    PostgresCteDomainRenderer,
    Mysql8DomainRenderer,
    build_join_predicate,
    assemble_domain_transport_sql,
    resolve_renderer,
    PIVOT_DOMAIN_TRANSPORT_REFUSED,
    SQLITE_MAX_BIND_PARAMS,
    MYSQL57_MAX_BIND_PARAMS,
)
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset.dialects.mysql import MySqlDialect


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _exec(conn: sqlite3.Connection, sql: str, params=()):
    """Execute SQL and return list of dicts."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _create_db() -> sqlite3.Connection:
    """In-memory SQLite with dim_product and fact_sales for oracle parity."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE dim_product (
            product_key INTEGER PRIMARY KEY,
            category_name TEXT
        );
        CREATE TABLE fact_sales (
            product_key INTEGER,
            customer_key INTEGER,
            sales_amount REAL
        );

        -- Electronics: 3 rows, 2 distinct customers (100, 101, 100)
        INSERT INTO dim_product VALUES (1, 'Electronics');
        -- Clothing: 2 rows, 1 distinct customer
        INSERT INTO dim_product VALUES (2, 'Clothing');
        -- Food: 1 row (not in domain for most tests)
        INSERT INTO dim_product VALUES (3, 'Food');
        -- NULL category (for null-matching test)
        INSERT INTO dim_product VALUES (4, NULL);

        INSERT INTO fact_sales VALUES (1, 100, 10.0);
        INSERT INTO fact_sales VALUES (1, 101, 20.0);
        INSERT INTO fact_sales VALUES (1, 100,  5.0);
        INSERT INTO fact_sales VALUES (2, 200, 30.0);
        INSERT INTO fact_sales VALUES (2, 200, 15.0);
        INSERT INTO fact_sales VALUES (3, 300, 50.0);
        INSERT INTO fact_sales VALUES (4, 400,  7.0);
    """)
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Renderer unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSqliteCteDomainRenderer:

    def _rnd(self):
        return SqliteCteDomainRenderer()

    def test_single_column_cte_shape(self):
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), ("Clothing",)),
        )
        frag = self._rnd().render(plan)

        assert frag.placement == "CTE"
        assert '"category_name"' in frag.cte_sql
        assert "VALUES (?), (?)" in frag.cte_sql
        assert frag.columns == ("category_name",)
        assert frag.domain_params == ("Electronics", "Clothing")
        # join_sql / join predicate are NOT part of fragment anymore
        assert frag.relation_alias == "_d"

    def test_multi_column_cte_shape(self):
        plan = DomainTransportPlan(
            columns=("category_name", "region"),
            tuples=(("A", "East"), ("B", "West")),
        )
        frag = self._rnd().render(plan)

        assert '"category_name", "region"' in frag.cte_sql
        assert "VALUES (?, ?), (?, ?)" in frag.cte_sql
        assert frag.domain_params == ("A", "East", "B", "West")

    def test_null_tuple_params(self):
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), (None,)),
        )
        frag = self._rnd().render(plan)
        assert frag.domain_params == ("Electronics", None)

    def test_null_safe_predicate_uses_is(self):
        rnd = self._rnd()
        pred = rnd.build_null_safe_predicate('p."cat"', '_d."cat"')
        assert pred == 'p."cat" IS _d."cat"'

    def test_params_limit_refuses(self):
        n = SQLITE_MAX_BIND_PARAMS + 1
        plan = DomainTransportPlan(
            columns=("c",),
            tuples=tuple((i,) for i in range(n)),
        )
        rnd = self._rnd()
        ok, reason = rnd.can_render(plan)
        assert not ok
        assert PIVOT_DOMAIN_TRANSPORT_REFUSED in reason

        with pytest.raises(NotImplementedError, match=PIVOT_DOMAIN_TRANSPORT_REFUSED):
            rnd.render(plan)

    def test_empty_tuples_not_renderable(self):
        plan = DomainTransportPlan(columns=("c",), tuples=())
        ok, _ = self._rnd().can_render(plan)
        assert not ok


class TestPostgresCteDomainRenderer:

    def _rnd(self):
        return PostgresCteDomainRenderer()

    def test_single_column_cte_shape(self):
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), ("Clothing",)),
        )
        frag = self._rnd().render(plan)

        assert frag.placement == "CTE"
        assert '"category_name"' in frag.cte_sql
        assert "VALUES (?), (?)" in frag.cte_sql
        assert frag.columns == ("category_name",)
        assert frag.domain_params == ("Electronics", "Clothing")
        assert frag.relation_alias == "_d"

    def test_null_safe_predicate_uses_is_not_distinct(self):
        rnd = self._rnd()
        pred = rnd.build_null_safe_predicate('p."cat"', '_d."cat"')
        assert pred == 'p."cat" IS NOT DISTINCT FROM _d."cat"'

    def test_params_limit_refuses(self):
        n = 10001
        plan = DomainTransportPlan(
            columns=("c",),
            tuples=tuple((i,) for i in range(n)),
        )
        rnd = self._rnd()
        ok, reason = rnd.can_render(plan)
        assert not ok
        assert PIVOT_DOMAIN_TRANSPORT_REFUSED in reason


class TestMysql8DomainRenderer:

    def _rnd(self):
        return Mysql8DomainRenderer()

    def test_single_column_cte_shape(self):
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), ("Clothing",)),
        )
        frag = self._rnd().render(plan)

        assert frag.placement == "CTE"
        assert "`category_name`" in frag.cte_sql
        assert '"category_name"' not in frag.cte_sql
        # Check UNION ALL SELECT
        assert "SELECT ?" in frag.cte_sql
        assert "UNION ALL SELECT ?" in frag.cte_sql
        assert frag.columns == ("category_name",)
        assert frag.domain_params == ("Electronics", "Clothing")
        assert frag.relation_alias == "_d"

    def test_null_safe_predicate_uses_spaceship(self):
        rnd = self._rnd()
        pred = rnd.build_null_safe_predicate('p."cat"', '_d."cat"')
        assert pred == 'p."cat" <=> _d."cat"'

    def test_join_predicate_uses_mysql_domain_identifier_quote(self):
        plan = DomainTransportPlan(
            columns=("product$categoryName",),
            tuples=(("Electronics",),),
        )
        rnd = self._rnd()
        frag = rnd.render(plan)
        join_sql = build_join_predicate(
            frag,
            {"product$categoryName": "p.`category_name`"},
            rnd,
        )
        assert "p.`category_name` <=> _d.`product$categoryName`" in join_sql

    def test_params_limit_refuses(self):
        n = MYSQL57_MAX_BIND_PARAMS + 1
        plan = DomainTransportPlan(
            columns=("c",),
            tuples=tuple((i,) for i in range(n)),
        )
        rnd = self._rnd()
        ok, reason = rnd.can_render(plan)
        assert not ok
        assert PIVOT_DOMAIN_TRANSPORT_REFUSED in reason


# ─────────────────────────────────────────────────────────────────────────────
# build_join_predicate tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildJoinPredicate:

    def _fragment(self, columns=("category_name",)):
        plan = DomainTransportPlan(
            columns=columns,
            tuples=(("A",) if len(columns) == 1 else ("A", "B"),),
        )
        rnd = SqliteCteDomainRenderer()
        return rnd.render(plan), rnd

    def test_single_column_predicate(self):
        frag, rnd = self._fragment(("category_name",))
        field_map = {"category_name": 'p."category_name"'}
        join_sql = build_join_predicate(frag, field_map, rnd)

        assert 'p."category_name" IS _d."category_name"' in join_sql
        assert join_sql.startswith("INNER JOIN _pivot_domain_transport AS _d ON")

    def test_multi_column_predicate(self):
        frag, rnd = self._fragment(("category_name", "region"))
        field_map = {
            "category_name": 'p."category_name"',
            "region": 't."region"',
        }
        join_sql = build_join_predicate(frag, field_map, rnd)

        assert 'p."category_name" IS _d."category_name"' in join_sql
        assert 't."region" IS _d."region"' in join_sql

    def test_missing_field_raises(self):
        frag, rnd = self._fragment(("category_name",))
        with pytest.raises(ValueError, match=PIVOT_DOMAIN_TRANSPORT_REFUSED):
            build_join_predicate(frag, {}, rnd)


# ─────────────────────────────────────────────────────────────────────────────
# assemble_domain_transport_sql tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAssembleDomainTransportSql:

    def _setup(self, columns=("category_name",)):
        plan = DomainTransportPlan(
            columns=columns,
            tuples=(("Electronics",), ("Clothing",)),
        )
        rnd = SqliteCteDomainRenderer()
        frag = rnd.render(plan)
        return frag, rnd

    def test_cte_appears_before_base_sql(self):
        frag, rnd = self._setup()
        base_sql = (
            'SELECT p."category_name", SUM(f."sales_amount") AS "total"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        sql, params = assemble_domain_transport_sql(
            base_sql, [], frag, field_map, rnd
        )

        assert sql.startswith("WITH _pivot_domain_transport")
        assert params == ["Electronics", "Clothing"]

    def test_join_injected_before_group_by(self):
        frag, rnd = self._setup()
        base_sql = (
            'SELECT p."category_name", SUM(f."sales_amount") AS "total"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        sql, _ = assemble_domain_transport_sql(base_sql, [], frag, field_map, rnd)

        join_pos = sql.upper().find("INNER JOIN _PIVOT_DOMAIN_TRANSPORT")
        group_pos = sql.upper().find("GROUP BY")
        assert 0 <= join_pos < group_pos, (
            f"INNER JOIN (pos={join_pos}) must precede GROUP BY (pos={group_pos})"
        )

    def test_join_injected_before_where(self):
        frag, rnd = self._setup()
        base_sql = (
            'SELECT p."category_name", SUM(f."sales_amount") AS "total"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'WHERE f."sales_amount" > ?\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        sql, params = assemble_domain_transport_sql(
            base_sql, [10.0], frag, field_map, rnd
        )

        join_pos = sql.upper().find("INNER JOIN _PIVOT_DOMAIN_TRANSPORT")
        where_pos = sql.upper().find("\nWHERE ")
        assert 0 <= join_pos < where_pos

        # CTE params before base WHERE param
        assert params == ["Electronics", "Clothing", 10.0]

    def test_domain_params_before_base_params_cte(self):
        frag, rnd = self._setup()
        base_sql = (
            'SELECT p."category_name"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'WHERE f."sales_amount" > ?\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        _, params = assemble_domain_transport_sql(
            base_sql, [5.0], frag, field_map, rnd
        )
        # domain params ("Electronics", "Clothing") must precede base param (5.0)
        assert params == ["Electronics", "Clothing", 5.0]


# ─────────────────────────────────────────────────────────────────────────────
# Resolver tests
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveRenderer:

    def test_sqlite_resolves(self):
        r = resolve_renderer(SqliteDialect())
        assert isinstance(r, SqliteCteDomainRenderer)

    def test_none_dialect_refuses(self):
        with pytest.raises(NotImplementedError, match=PIVOT_DOMAIN_TRANSPORT_REFUSED):
            resolve_renderer(None)

    def test_mysql_resolves(self):
        r = resolve_renderer(MySqlDialect())
        assert isinstance(r, Mysql8DomainRenderer)

    def test_postgres_resolves(self):
        class PgDialect:
            def name(self): return "postgres"
        r = resolve_renderer(PgDialect())
        assert isinstance(r, PostgresCteDomainRenderer)

    def test_mysql57_refuses(self):
        class MySql57Dialect:
            def name(self): return "mysql5.7"
        with pytest.raises(NotImplementedError, match=PIVOT_DOMAIN_TRANSPORT_REFUSED):
            resolve_renderer(MySql57Dialect())


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Oracle Parity — assembled SQL executed directly
# ─────────────────────────────────────────────────────────────────────────────
#
# Each test MUST:
#  1. Build a base_sql that the assembler will process.
#  2. Call assemble_domain_transport_sql() to produce the final SQL.
#  3. Execute the assembled SQL on the SQLite DB.
#  4. Execute an independent hand-written oracle SQL on the same DB.
#  5. Assert the two results are equal.
#
# This proves the assembler produces correct, executable SQL — not just
# that the target SQL semantics are correct.

class TestSqliteOracleParity:

    def _base_sql_and_map(self):
        """Standard base SQL with fact+dim join and a field_sql_map."""
        base_sql = (
            'SELECT p."category_name", SUM(f."sales_amount") AS "total_sales"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        return base_sql, field_map

    def _base_sql_count_distinct_and_map(self):
        """Base SQL with COUNT(DISTINCT) for non-additive test."""
        base_sql = (
            'SELECT p."category_name",\n'
            '       COUNT(DISTINCT f."customer_key") AS "unique_customers"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}
        return base_sql, field_map

    def _render(self, plan):
        rnd = SqliteCteDomainRenderer()
        frag = rnd.render(plan)
        return frag, rnd

    def test_additive_sum_parity(self):
        """SUM(sales_amount) for domain {Electronics, Clothing}.

        Assembled SQL executed directly; result compared to hand-written oracle.
        """
        conn = _create_db()
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), ("Clothing",)),
        )
        frag, rnd = self._render(plan)
        base_sql, field_map = self._base_sql_and_map()

        sql, params = assemble_domain_transport_sql(
            base_sql, [], frag, field_map, rnd
        )
        result = sorted(_exec(conn, sql, params), key=lambda r: r["category_name"])

        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) AS total_sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name IN ('Electronics', 'Clothing')
            GROUP BY p.category_name
        """
        oracle = sorted(_exec(conn, oracle_sql), key=lambda r: r["category_name"])

        assert len(result) == 2
        assert result == oracle
        conn.close()

    def test_non_additive_count_distinct_parity(self):
        """COUNT(DISTINCT customer_key) for domain {Electronics}.

        Electronics rows: customer 100, 101, 100 → 2 distinct customers.

        This proves the domain JOIN happens BEFORE aggregation: if it were
        a post-aggregation re-SUM wrapper, COUNT(DISTINCT) would be wrong.
        The assembled SQL must produce ``unique_customers = 2``, matching
        the oracle.
        """
        conn = _create_db()
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",),),
        )
        frag, rnd = self._render(plan)
        base_sql, field_map = self._base_sql_count_distinct_and_map()

        sql, params = assemble_domain_transport_sql(
            base_sql, [], frag, field_map, rnd
        )
        result = _exec(conn, sql, params)

        oracle_sql = """
            SELECT p.category_name,
                   COUNT(DISTINCT f.customer_key) AS unique_customers
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name = 'Electronics'
            GROUP BY p.category_name
        """
        oracle = _exec(conn, oracle_sql)

        assert len(result) == 1
        assert result[0]["unique_customers"] == 2
        assert result == oracle
        conn.close()

    def test_null_domain_member_parity(self):
        """Domain containing NULL member matched via SQLite IS operator.

        NULL category in dim_product (product_key=4, sales=7.0).
        Domain = {Electronics, NULL}.
        """
        conn = _create_db()
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), (None,)),
        )
        frag, rnd = self._render(plan)
        base_sql, field_map = self._base_sql_and_map()

        sql, params = assemble_domain_transport_sql(
            base_sql, [], frag, field_map, rnd
        )
        result = sorted(
            _exec(conn, sql, params),
            key=lambda r: str(r["category_name"]),
        )

        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) AS total_sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name = 'Electronics' OR p.category_name IS NULL
            GROUP BY p.category_name
        """
        oracle = sorted(
            _exec(conn, oracle_sql),
            key=lambda r: str(r["category_name"]),
        )

        assert len(result) == 2
        assert result == oracle
        conn.close()

    def test_params_ordering_with_base_where_param(self):
        """For CTE strategy, domain params must precede base WHERE params.

        The assembled SQL has:
          WITH ... AS (VALUES (?, ?))   ← positions 0,1 → domain params
          SELECT ...
          FROM ...
          WHERE f.sales_amount > ?      ← position 2 → base param
          GROUP BY ...

        So params must be [domain_1, domain_2, base_1].
        """
        conn = _create_db()
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=(("Electronics",), ("Clothing",)),
        )
        frag, rnd = self._render(plan)

        base_sql = (
            'SELECT p."category_name", SUM(f."sales_amount") AS "total_sales"\n'
            'FROM "fact_sales" AS f\n'
            'LEFT JOIN "dim_product" AS p ON f."product_key" = p."product_key"\n'
            'WHERE f."sales_amount" > ?\n'
            'GROUP BY p."category_name"'
        )
        field_map = {"category_name": 'p."category_name"'}

        sql, params = assemble_domain_transport_sql(
            base_sql, [10.0], frag, field_map, rnd
        )

        # Verify params order
        assert params == ["Electronics", "Clothing", 10.0]

        # Execute and compare to oracle
        result = sorted(_exec(conn, sql, params), key=lambda r: r["category_name"])

        oracle_sql = """
            SELECT p.category_name, SUM(f.sales_amount) AS total_sales
            FROM fact_sales f
            LEFT JOIN dim_product p ON f.product_key = p.product_key
            WHERE p.category_name IN ('Electronics', 'Clothing')
              AND f.sales_amount > 10.0
            GROUP BY p.category_name
        """
        oracle = sorted(_exec(conn, oracle_sql), key=lambda r: r["category_name"])

        assert result == oracle
        conn.close()

    def test_large_domain_smaller_than_limit(self):
        """Domain with many tuples (but under 999 param limit) assembles and executes."""
        conn = _create_db()
        # 50 tuples of (str, ) → 50 params, well under limit
        all_cats = [("Electronics",), ("Clothing",)] + [(f"Cat{i}",) for i in range(48)]
        plan = DomainTransportPlan(
            columns=("category_name",),
            tuples=tuple(all_cats),
        )
        frag, rnd = self._render(plan)
        base_sql, field_map = self._base_sql_and_map()

        sql, params = assemble_domain_transport_sql(
            base_sql, [], frag, field_map, rnd
        )
        # Should execute without error; only Electronics and Clothing rows exist
        result = _exec(conn, sql, params)
        assert len(result) == 2  # Only these two exist in the DB
        conn.close()
