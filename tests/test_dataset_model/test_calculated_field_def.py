"""Tests for CalculatedFieldDef.expression early-fail hook (v1.4 M4 Step 4.4).

Covers REQ-FORMULA-EXTEND §4.3: the Pydantic ``model_validator`` runs
``FormulaCompiler.validate_syntax`` at QM load time so invalid formulas
surface as ``ValidationError`` with a clear pointer to the offending
field, instead of cryptic SQL errors at the first query.

Scope carve-outs verified here:
  - Window-function calcs bypass the hook (``RANK() / ROW_NUMBER()`` etc.)
  - Phase 3 AST-only nodes (method calls, ternary, null-coalescing) are
    accepted at load time and validated later by the service.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from foggy.dataset_model.definitions.query_request import CalculatedFieldDef


class TestExpressionSyntaxEarlyFail:
    """Legal expressions load; illegal ones raise ValidationError."""

    # ------- legal expressions (no raise) ----------------------------------

    def test_simple_arithmetic_loads_ok(self):
        cf = CalculatedFieldDef(name="net", expression="a - b")
        assert cf.expression == "a - b"

    def test_whitelisted_function_loads_ok(self):
        cf = CalculatedFieldDef(name="nullsafe", expression="coalesce(a, b)")
        assert cf.expression == "coalesce(a, b)"

    def test_aggregation_at_outermost_loads_ok(self):
        cf = CalculatedFieldDef(name="total", expression="sum(salesAmount)")
        assert cf.expression == "sum(salesAmount)"

    def test_if_with_in_loads_ok(self):
        cf = CalculatedFieldDef(
            name="isHot",
            expression="if(status in ('a', 'b'), 1, 0)",
        )
        assert "status" in cf.expression

    # ------- illegal expressions (raise) -----------------------------------

    def test_malformed_expression_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CalculatedFieldDef(name="bad", expression="amount +")
        msg = str(exc_info.value)
        assert "Invalid calculated field expression" in msg
        assert "amount +" in msg
        assert "bad" in msg  # field name surfaced

    def test_unsupported_power_operator_raises(self):
        """``**`` is deliberately outside Spec v1 — must surface early."""
        with pytest.raises(ValidationError) as exc_info:
            CalculatedFieldDef(name="squared", expression="amount ** 2")
        assert "Invalid calculated field expression" in str(exc_info.value)

    def test_aggregation_not_outermost_raises(self):
        """``sum(a) + 1`` nests agg inside arithmetic — §4.1 violation."""
        with pytest.raises(ValidationError) as exc_info:
            CalculatedFieldDef(
                name="bad_agg",
                expression="sum(salesAmount) + 1",
            )
        assert "Invalid calculated field expression" in str(exc_info.value)
        # The message chains the compiler's semantic label so developers
        # can grep it in logs.
        assert (
            "not the outermost" in str(exc_info.value)
            or "aggregation" in str(exc_info.value).lower()
        )

    def test_unknown_function_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CalculatedFieldDef(name="bad_fn", expression="lpad(name, 3, '0')")
        assert "Invalid calculated field expression" in str(exc_info.value)
        assert "lpad" in str(exc_info.value)

    # ------- carve-outs ----------------------------------------------------

    def test_window_function_expression_bypasses_hook(self):
        """Window-function calcs route through the legacy SQL path; the
        Spec v1 whitelist does not cover ``RANK() / ROW_NUMBER() / LAG()``
        so we intentionally do NOT reject them at load time."""
        cf = CalculatedFieldDef(
            name="rnk",
            expression="RANK()",
            partition_by=["product"],
            window_order_by=[{"field": "salesAmount", "dir": "desc"}],
        )
        assert cf.expression == "RANK()"
        assert cf.is_window_function()

    def test_window_avg_moving_average_loads(self):
        """``AVG(salesAmount)`` with a window spec is a moving-average
        calc — must not be blocked by the early-fail hook."""
        cf = CalculatedFieldDef(
            name="ma7",
            expression="AVG(salesAmount)",
            partition_by=["product"],
            window_order_by=[{"field": "date", "dir": "asc"}],
            window_frame="ROWS BETWEEN 6 PRECEDING AND CURRENT ROW",
        )
        assert cf.is_window_function()

    def test_method_call_expression_loads_phase3(self):
        """Phase 3 AST feature — ``name.startsWith('A')`` stays loadable so
        the opt-in ``use_ast_expression_compiler=True`` path can still
        consume it.  FormulaCompiler rejects it, but we silently accept
        at the model level per §4.4's Phase 3 carve-out."""
        cf = CalculatedFieldDef(name="isA", expression="name.startsWith('A')")
        assert cf.expression == "name.startsWith('A')"

    def test_empty_expression_skips_hook(self):
        """Empty-string ``expression`` bypasses the hook by design (same
        carve-out as the doc's ``if not v: return v`` guard).

        The downstream service will still reject an empty expression at
        compile time; the early-fail hook only activates on non-empty
        strings so legacy QM load paths that defer expression wiring do
        not regress.
        """
        cf = CalculatedFieldDef(name="e", expression="")
        assert cf.expression == ""

    def test_missing_expression_is_required_field(self):
        """``expression`` is a required Pydantic field — constructing
        without it still raises ValidationError (required-field path)."""
        with pytest.raises(ValidationError):
            CalculatedFieldDef(name="e")  # type: ignore[call-arg]
