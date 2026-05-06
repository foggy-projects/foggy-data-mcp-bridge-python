"""Regression tests for BUG-compose-window-calculated-field-alias-sql-leak.

Fail-closed: calculatedFields.windowOrderBy that references an inline
aggregate alias or a raw expression must be rejected BEFORE reaching the
SQL execution layer — never leaked to PostgreSQL as ``totalsales`` / hints.

Test matrix
-----------
T1  inline agg alias in windowOrderBy              → ComposeCompileError (phase=compile)
T2  raw aggregate expression in windowOrderBy      → ComposeCompileError (phase=compile)
T3  calc-field-to-calc-field windowOrderBy ref     → allowed (compiled_calcs path)
T4  valid QM measure field in windowOrderBy        → allowed (SQL contains OVER ORDER BY)
T5  column name that happens to contain parens     → rejected (raw-expression guard)
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.compilation import (
    ComposeCompileError,
    compile_plan_to_sql,
)
from foggy.dataset_model.engine.compose.plan import from_


# ---------------------------------------------------------------------------
# Shared fixture shorthand
# ---------------------------------------------------------------------------

def _compile(plan, svc, ctx, dialect="sqlite"):
    return compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect=dialect)


# ===========================================================================
# T1 — inline aggregate alias in windowOrderBy → rejected
# ===========================================================================


class TestWindowCfInlineAggAliasRejected:
    """windowOrderBy references a name that is not a QM field — simulating
    the case where the user passes an alias that only exists as an output
    label (e.g. from another calculatedField aggregate result or a columns
    alias), but is not a resolvable base measure or dimension.

    The canonical failure: field 'nonExistentAggAlias' reaches _resolve_single_field
    which returns the raw name → 'nonexistentaggalias' leaks to PostgreSQL."""

    def test_nonexistent_alias_in_window_order_raises(self, svc, ctx):
        """Scenario: RANK() OVER (ORDER BY totalSales DESC) where 'totalSales'
        is NOT a QM measure, dimension, or compiled calc-field. Simulates the
        user providing an output alias as if it were an orderable column.

        Expected: ComposeCompileError (phase=compile) before SQL is built.
        Message must name 'totalSales' so the LLM caller can understand.
        """
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName", "salesAmount"],
            calculated_fields=[
                # 'totalSales' is only an alias name — not a QM field.
                # windowOrderBy referencing it as if it were a column must fail.
                {
                    "name": "salesRank",
                    "expression": "RANK()",
                    "partition_by": ["product$categoryName"],
                    "window_order_by": [{"field": "totalSales", "dir": "desc"}],
                },
            ],
            group_by=["product$categoryName"],
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            _compile(plan, svc, ctx)

        err = exc_info.value
        assert err.phase == "compile", (
            f"expected phase='compile', got {err.phase!r}"
        )
        # Message must mention the offending alias so the user understands.
        cause_msg = str(err.__cause__ or err)
        assert "totalSales" in cause_msg, (
            f"expected 'totalSales' in error message, got: {cause_msg!r}"
        )
        # Physical SQL hints must NOT appear.
        assert "HINT" not in cause_msg.upper(), (
            f"physical SQL hint leaked in error: {cause_msg!r}"
        )

    def test_agg_calc_field_alias_window_order_raises_when_unresolvable(self, svc, ctx):
        """Simulates the exact BUG: user writes
            calculatedFields: [
              {name: 'sumAmt', expression: 'amountTotal', agg: 'SUM'},
              {name: 'rank', expression: 'RANK()',
               windowOrderBy: [{field: 'sumAmtAlias', dir: 'desc'}]}
            ]
        where 'sumAmtAlias' doesn't exist in the QM at all.
        (In the real bug, the user wrote an alias for the agg column and
        tried to reference it by that alias name.)
        """
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName"],
            calculated_fields=[
                {
                    "name": "r",
                    "expression": "RANK()",
                    # 'amountTotalAlias' is not a QM field name
                    "windowOrderBy": [{"field": "amountTotalAlias", "dir": "desc"}],
                },
            ],
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            _compile(plan, svc, ctx)

        assert exc_info.value.phase == "compile"
        cause_msg = str(exc_info.value.__cause__ or exc_info.value)
        assert "amountTotalAlias" in cause_msg


# ===========================================================================
# T2 — raw aggregate expression in windowOrderBy → rejected
# ===========================================================================


class TestWindowCfRawExpressionRejected:
    """windowOrderBy.field contains a parenthesis — it's a raw SQL expression
    rather than a field name reference.  Must be caught early."""

    def test_raw_aggregate_expression_is_rejected(self, svc, ctx):
        """Scenario: windowOrderBy: [{field: 'sum(salesAmount)', dir: 'desc'}]
        The engine must reject this — 'sum(salesAmount)' is not a field name."""
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName"],
            calculated_fields=[
                {
                    "name": "catRank",
                    "expression": "RANK()",
                    "partition_by": [],
                    "window_order_by": [
                        {"field": "sum(salesAmount)", "dir": "desc"}
                    ],
                },
            ],
            group_by=["product$categoryName"],
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            _compile(plan, svc, ctx)

        err = exc_info.value
        assert err.phase == "compile"
        cause_msg = str(err.__cause__ or err)
        # At minimum the field value must appear in the message.
        assert "sum(salesAmount)" in cause_msg or "COMPOSE_WINDOW_ORDER_BY" in cause_msg

    def test_paren_in_field_is_always_rejected_regardless_of_model(self, svc, ctx):
        """Even if the outer expression looks innocent, any '(' in the field
        name means it's a raw expression, not a column reference."""
        plan = from_(
            model="FactSalesModel",
            columns=["orderStatus$caption"],
            calculated_fields=[
                {
                    "name": "r",
                    "expression": "ROW_NUMBER()",
                    "window_order_by": [
                        {"field": "count(orderId)", "dir": "asc"}
                    ],
                },
            ],
        )

        with pytest.raises(ComposeCompileError):
            _compile(plan, svc, ctx)


# ===========================================================================
# T3 — calc-field-to-calc-field windowOrderBy reference → allowed
# ===========================================================================


class TestWindowCfCalcTocalcAllowed:
    """A windowOrderBy.field that references a PREVIOUSLY compiled calc field
    must be allowed (compiled_calcs lookup path)."""

    def test_preceding_calc_field_as_window_order_is_allowed(self, svc, ctx):
        """salesAmt is a scalar calc → allowed as ORDER target for a later
        window calc via the compiled_calcs path.  No error expected."""
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName"],
            calculated_fields=[
                # scalar calc — becomes a compiled_calcs entry
                {
                    "name": "salesAmt",
                    "expression": "salesAmount * 1.0",
                },
                # window calc ordering by the scalar calc above
                {
                    "name": "catRank",
                    "expression": "RANK()",
                    "partition_by": ["product$categoryName"],
                    "window_order_by": [{"field": "salesAmt", "dir": "desc"}],
                },
            ],
        )

        # Must not raise — salesAmt is a compiled_calcs entry known at the
        # time catRank is processed (topo-sort ensures ordering).
        composed = _compile(plan, svc, ctx)
        assert composed.sql  # non-empty SQL emitted


# ===========================================================================
# T4 — valid QM measure in windowOrderBy → allowed
# ===========================================================================


class TestWindowCfValidMeasureAllowed:
    """windowOrderBy referencing a legitimate QM measure field (salesAmount)
    is the canonical correct usage and must succeed."""

    def test_qm_measure_in_window_order_is_accepted(self, svc, ctx):
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName", "salesAmount"],
            calculated_fields=[
                {
                    "name": "catRank",
                    "expression": "RANK()",
                    "partition_by": [],
                    "window_order_by": [{"field": "salesAmount", "dir": "desc"}],
                },
            ],
            group_by=["product$categoryName"],
        )

        composed = _compile(plan, svc, ctx)
        assert composed.sql
        # Window OVER clause must appear in the emitted SQL.
        assert "OVER" in composed.sql.upper()
        assert "ORDER BY" in composed.sql.upper()

    def test_qm_dimension_caption_in_window_order_is_accepted(self, svc, ctx):
        """Dimension property references (salesDate$caption) are valid QM
        fields and must be accepted in windowOrderBy."""
        plan = from_(
            model="FactSalesModel",
            columns=["salesDate$caption", "salesAmount"],
            calculated_fields=[
                {
                    "name": "cumSales",
                    "expression": "salesAmount",
                    "agg": "SUM",
                    "window_order_by": [{"field": "salesDate$caption", "dir": "asc"}],
                    "window_frame": "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
                },
            ],
        )

        composed = _compile(plan, svc, ctx)
        assert composed.sql
        assert "OVER" in composed.sql.upper()


# ===========================================================================
# T5 — windowOrderBy.field with unresolvable non-model name → rejected
# ===========================================================================


class TestWindowCfUnresolvableFieldRejected:
    """A windowOrderBy.field that is neither a QM measure/dimension,
    a compiled_calcs entry, nor a raw expression with '('
    but is simply not found in the model → fail-closed."""

    def test_completely_unknown_field_is_rejected(self, svc, ctx):
        """Field 'ghostField' does not exist in the model and has no
        prior compiled_calcs entry — must be rejected before SQL."""
        plan = from_(
            model="FactSalesModel",
            columns=["product$categoryName"],
            calculated_fields=[
                {
                    "name": "r",
                    "expression": "RANK()",
                    "window_order_by": [{"field": "ghostField", "dir": "asc"}],
                },
            ],
        )

        with pytest.raises(ComposeCompileError) as exc_info:
            _compile(plan, svc, ctx)

        err = exc_info.value
        assert err.phase == "compile"
        cause_msg = str(err.__cause__ or err)
        assert "ghostField" in cause_msg
