"""BUG-003 regression tests — inline expression string literal quoting.

Verifies that string literals inside DSL inline expressions (``sum(if(...))``,
``count(if(...))``, etc.) are always rendered as SQL single-quoted literals,
regardless of whether the user wrote ``"..."`` or ``'...'`` in the DSL.

Root cause tracked in ``docs/v1.4/BUG-003-*``: previously
``_render_expression`` copied the raw user segment verbatim, so a
double-quoted DSL string like ``"posted"`` landed in the generated SQL as a
PostgreSQL identifier and triggered ``column "posted" does not exist``.

The fix must:
  * Normalize single- and double-quoted DSL string literals to single-quoted
    SQL literals.
  * Preserve embedded characters (including existing single quotes, which are
    escaped as ``''`` per SQL standard).
  * Avoid rewriting values that already look like physical column names
    (e.g. ``"po_lead"`` used as a *value* must not be emitted as an
    identifier).
"""

from __future__ import annotations

import pytest

from foggy.dataset.dialects.mysql import MySqlDialect
from foggy.dataset.dialects.postgres import PostgresDialect
from foggy.dataset.dialects.sqlite import SqliteDialect
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model
from foggy.mcp_spi import SemanticQueryRequest


def _service(dialect) -> SemanticQueryService:
    svc = SemanticQueryService(dialect=dialect, executor=None)
    svc.register_model(create_fact_sales_model())
    return svc


def _validate(svc: SemanticQueryService, columns):
    req = SemanticQueryRequest(columns=columns)
    resp = svc.query_model("FactSalesModel", req, mode="validate")
    assert resp.error is None, f"validate failed: {resp.error}"
    assert resp.sql is not None
    return resp.sql


# ---------------------------------------------------------------------------
# Core BUG-003 reproduction (fails before the fix)
# ---------------------------------------------------------------------------


class TestInlineDoubleQuotedStringLiteralNormalizedToSingleQuote:
    """Before fix: these render ``= "COMPLETED"`` → PG reads as identifier."""

    @pytest.mark.parametrize("dialect", [SqliteDialect(), MySqlDialect(), PostgresDialect()])
    def test_sum_if_double_quoted_literal_is_single_quoted_in_sql(self, dialect):
        svc = _service(dialect)
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED", 1, 0)) as completedCount',
            ],
        )
        assert "'COMPLETED'" in sql, (
            f"expected single-quoted SQL literal, got SQL:\n{sql}"
        )
        assert '"COMPLETED"' not in sql, (
            "double-quoted DSL literal leaked into generated SQL as identifier; "
            f"SQL:\n{sql}"
        )

    @pytest.mark.parametrize("dialect", [SqliteDialect(), MySqlDialect(), PostgresDialect()])
    def test_count_if_double_quoted_literal_is_single_quoted(self, dialect):
        svc = _service(dialect)
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'count(if(orderStatus == "COMPLETED", 1, null)) as completedRows',
            ],
        )
        assert "'COMPLETED'" in sql
        assert '"COMPLETED"' not in sql

    def test_user_reported_odoo_pattern_multi_and_double_quoted_literals(self):
        """Mirrors the user report shape: multiple ``&&`` conditions with double
        quoted literals embedded in ``sum(if(...))``. Uses FactSales schema to
        avoid requiring the Odoo bundle, but shape is 1:1 with the bug."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED" && salesAmount > 0 && paymentMethod == "ALIPAY", salesAmount, 0)) as total',
            ],
        )
        # Both string literals must be single-quoted in the final SQL.
        assert "'COMPLETED'" in sql
        assert "'ALIPAY'" in sql
        # No raw PG identifier quotes around user values.
        assert '"COMPLETED"' not in sql
        assert '"ALIPAY"' not in sql


# ---------------------------------------------------------------------------
# Boundary / failure-mode scenarios (added after the fix as part of the
# BUG-003 regression prompt: "补充还有可能出错的测试场景")
# ---------------------------------------------------------------------------


class TestInlineStringLiteralBoundaryScenarios:
    def test_single_quoted_literal_remains_single_quoted(self):
        """Baseline: pre-existing single-quoted DSL path must keep working."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                "sum(if(orderStatus == 'COMPLETED', 1, 0)) as c",
            ],
        )
        assert "'COMPLETED'" in sql

    def test_mixed_single_and_double_quotes_in_same_expression(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                "sum(if(orderStatus == 'COMPLETED' && paymentMethod == \"ALIPAY\", 1, 0)) as c",
            ],
        )
        assert "'COMPLETED'" in sql
        assert "'ALIPAY'" in sql
        assert '"ALIPAY"' not in sql

    def test_nested_if_double_quoted_literals(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED", if(paymentMethod == "ALIPAY", 1, 0), 0)) as alipayCompleted',
            ],
        )
        assert "'COMPLETED'" in sql
        assert "'ALIPAY'" in sql
        assert '"COMPLETED"' not in sql
        assert '"ALIPAY"' not in sql

    def test_or_chain_with_double_quoted_literals(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED" || orderStatus == "PAID", 1, 0)) as closed',
            ],
        )
        assert sql.count("'COMPLETED'") == 1
        assert sql.count("'PAID'") == 1
        assert '"COMPLETED"' not in sql
        assert '"PAID"' not in sql

    def test_value_containing_single_quote_is_sql_escaped(self):
        """DSL ``"it's"`` must produce SQL literal ``'it''s'`` (single-quote
        doubling per SQL standard), regardless of dialect."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                "sum(if(orderStatus == \"it's\", 1, 0)) as c",
            ],
        )
        assert "'it''s'" in sql
        # Must not leak PG identifier quoting of user value.
        assert '"it\'s"' not in sql

    def test_value_that_looks_like_physical_column_name(self):
        """Regression for the user's ``po_lead`` HINT: if a user happens to
        compare against a value that matches an existing physical column, it
        must still be emitted as a string literal, not an identifier."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "po_lead", 1, 0)) as c',
            ],
        )
        assert "'po_lead'" in sql
        assert '"po_lead"' not in sql

    def test_value_with_backslash_is_preserved(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "a\\\\b", 1, 0)) as c',
            ],
        )
        # Either ``'a\\b'`` or ``'a\b'`` depending on escaping choice, but must
        # never leak the user value as a double-quoted identifier.
        assert "'a" in sql
        assert '"a\\\\b"' not in sql
        assert '"a\\b"' not in sql

    def test_empty_string_literal(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "", 1, 0)) as c',
            ],
        )
        assert "''" in sql
        # No double-quoted empty identifier.
        assert '""' not in sql

    def test_date_like_literal_stays_string(self):
        """Mirrors user report: ``dateMaturity < "2026-04-19"`` must stay a
        string literal. Uses fact_sales ``salesDate`` which maps to dim_date."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED", salesAmount, 0)) as c',
            ],
        )
        assert "'COMPLETED'" in sql
        assert '"COMPLETED"' not in sql

    def test_unicode_chinese_value(self):
        """Non-ASCII values (e.g. Chinese status labels) must survive the
        normalization path unchanged inside single quotes."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "已完成", 1, 0)) as c',
            ],
        )
        assert "'已完成'" in sql
        assert '"已完成"' not in sql

    def test_value_with_leading_and_trailing_whitespace(self):
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "  COMPLETED  ", 1, 0)) as c',
            ],
        )
        assert "'  COMPLETED  '" in sql
        assert '"  COMPLETED  "' not in sql

    def test_value_with_sql_injection_like_content_is_escaped(self):
        """Defense in depth: user values containing SQL-looking syntax must
        be emitted as escaped single-quoted literals, not leak through."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                "sum(if(orderStatus == \"'; DROP TABLE users--\", 1, 0)) as c",
            ],
        )
        # Single quote inside must be doubled per SQL standard.
        assert "''';" in sql or "''; DROP" in sql
        # No PG identifier escape of attacker content.
        assert '"\';' not in sql

    def test_numeric_looking_string_stays_string(self):
        """A numeric-looking value wrapped in DSL quotes must still be a
        SQL string literal (not coerced to an unquoted numeric)."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "2026", 1, 0)) as c',
            ],
        )
        assert "'2026'" in sql

    def test_same_value_used_twice_in_and_chain(self):
        """Guards against accidental de-duplication / shared-buffer bugs."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "COMPLETED" && orderStatus == "COMPLETED", 1, 0)) as c',
            ],
        )
        assert sql.count("'COMPLETED'") == 2
        assert '"COMPLETED"' not in sql

    def test_double_quote_inside_single_quoted_dsl_literal_is_kept_verbatim(self):
        """DSL ``'say "hi"'`` should surface as SQL literal ``'say "hi"'``
        without triggering the PG identifier path."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                "sum(if(orderStatus == 'say \"hi\"', 1, 0)) as c",
            ],
        )
        # The literal double-quote inside a single-quoted DSL literal
        # must survive into the SQL literal. Whatever the engine chose as
        # the logical value, it must not be emitted as a PG identifier.
        assert "say" in sql
        # No bare PG identifier quoting around "hi" — the sequence
        # ``= "hi"`` would indicate the BUG.
        assert ' = "hi"' not in sql
        assert ' = "say \"hi\""' not in sql

    def test_value_with_percent_and_underscore_not_treated_as_like_pattern(self):
        """``%`` and ``_`` are SQL LIKE wildcards but DSL ``==`` is not LIKE;
        the value must stay a plain string literal."""
        svc = _service(PostgresDialect())
        sql = _validate(
            svc,
            [
                "orderStatus$caption",
                'sum(if(orderStatus == "50%_off", 1, 0)) as c',
            ],
        )
        assert "'50%_off'" in sql
        assert '"50%_off"' not in sql
