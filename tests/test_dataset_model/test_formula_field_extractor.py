"""Unit tests for formula_field_extractor.

Tests the extraction of QM field names from formula expressions used in
columnGroups.formula items, specifically the AR measures from
OdooAccountMoveLineQueryModel.qm.
"""

import pytest
from foggy.dataset_model.semantic.formula_field_extractor import extract_formula_fields


class TestExtractFormulaFields:
    """Tests for the formula field extractor."""

    def test_empty_expression(self):
        assert extract_formula_fields("") == set()
        assert extract_formula_fields(None) == set()

    def test_simple_sum(self):
        result = extract_formula_fields("sum(amountResidual)")
        assert result == {"amountResidual"}

    def test_ar_outstanding_amount(self):
        """Full AR outstanding formula from OdooAccountMoveLineQueryModel.qm."""
        expr = (
            "sum(if(move$moveType == 'out_invoice'"
            " && move$state == 'posted'"
            " && move$paymentState in ('not_paid', 'partial', 'in_payment'),"
            " amountResidual, 0))"
        )
        result = extract_formula_fields(expr)
        # Must include the referenced QM fields
        assert "amountResidual" in result
        assert "move$moveType" in result
        assert "move$state" in result
        assert "move$paymentState" in result
        # Must NOT include SQL keywords or function names
        assert "sum" not in result
        assert "if" not in result
        assert "in" not in result
        assert "and" not in result

    def test_ar_overdue_amount(self):
        """AR overdue formula — adds dateMaturity reference."""
        expr = (
            "sum(if(move$moveType == 'out_invoice'"
            " && move$state == 'posted'"
            " && move$paymentState in ('not_paid', 'partial', 'in_payment')"
            " && dateMaturity < now(),"
            " amountResidual, 0))"
        )
        result = extract_formula_fields(expr)
        assert "amountResidual" in result
        assert "dateMaturity" in result
        assert "move$moveType" in result
        # now() is a function call; 'now' should be in reserved words
        assert "now" not in result

    def test_ar_overdue_customer_count(self):
        """AR overdue customer count formula — uses count(distinct(if(...))), partner$id."""
        expr = (
            "count(distinct(if(move$moveType == 'out_invoice'"
            " && move$state == 'posted'"
            " && move$paymentState in ('not_paid', 'partial', 'in_payment')"
            " && dateMaturity < now(),"
            " partner$id, null)))"
        )
        result = extract_formula_fields(expr)
        assert "partner$id" in result
        assert "dateMaturity" in result
        assert "move$moveType" in result
        # Reserved words / functions must be excluded
        assert "count" not in result
        assert "distinct" not in result
        assert "null" not in result
        assert "now" not in result

    def test_string_literals_excluded(self):
        """String literal content must not be tokenized as field names."""
        expr = "sum(if(status == 'out_invoice', amount, 0))"
        result = extract_formula_fields(expr)
        # 'out_invoice' is a string literal, should not appear
        assert "out_invoice" not in result
        assert "status" in result
        assert "amount" in result

    def test_dimension_field_with_dollar(self):
        """$ separator fields like move$state should be extracted as a single token."""
        expr = "sum(if(order$status == 'completed', revenue, 0))"
        result = extract_formula_fields(expr)
        # The whole token including $ should be present
        assert "order$status" in result
        assert "revenue" in result

    def test_numeric_literals_excluded(self):
        """Pure numeric tokens should not appear in output."""
        expr = "sum(if(score >= 100, bonus, 0))"
        result = extract_formula_fields(expr)
        assert "0" not in result
        assert "100" not in result
        assert "score" in result
        assert "bonus" in result


class TestFormulaAccessibility:
    """Integration test for formula field accessibility checking."""

    def test_accessible_when_all_referenced_visible(self):
        from foggy.dataset_model.semantic.service import SemanticQueryService
        calc = {
            "name": "arOutstandingAmount",
            "expression": "sum(if(move$moveType == 'x', amountResidual, 0))",
        }
        visible = {"move", "amountResidual"}  # base names for dim-qualified fields
        assert SemanticQueryService._is_formula_accessible(calc, visible) is True

    def test_denied_when_referenced_field_missing(self):
        from foggy.dataset_model.semantic.service import SemanticQueryService
        calc = {
            "name": "arOutstandingAmount",
            "expression": "sum(if(move$moveType == 'x', amountResidual, 0))",
        }
        # amountResidual is denied
        visible = {"move"}
        assert SemanticQueryService._is_formula_accessible(calc, visible) is False

    def test_accessible_when_no_governance(self):
        from foggy.dataset_model.semantic.service import SemanticQueryService
        calc = {
            "name": "arOutstandingAmount",
            "expression": "sum(amountResidual)",
        }
        assert SemanticQueryService._is_formula_accessible(calc, None) is True

    def test_fail_closed_when_no_expression(self):
        from foggy.dataset_model.semantic.service import SemanticQueryService
        calc = {"name": "arOutstandingAmount", "expression": ""}
        # No expression → fail-closed when governance is active
        visible = {"amountResidual"}
        assert SemanticQueryService._is_formula_accessible(calc, visible) is False

class TestDateFunctionsNotTreatedAsFields:
    """Explicit tests that date/time formula functions are excluded from field references.

    These functions are used in columnGroups.formula expressions (e.g. AR measures)
    and must not be treated as QM field references by the extractor or the
    field validator.  Regression test for the Phase 3 bridge cleanup.
    """

    def test_now_is_not_a_field_reference(self):
        result = extract_formula_fields("dateMaturity < now()")
        assert "dateMaturity" in result
        assert "now" not in result

    def test_today_is_not_a_field_reference(self):
        result = extract_formula_fields("dateOrder >= today()")
        assert "dateOrder" in result
        assert "today" not in result

    def test_date_diff_is_not_a_field_reference(self):
        result = extract_formula_fields("date_diff(dateMaturity, now())")
        assert "dateMaturity" in result
        assert "date_diff" not in result
        assert "now" not in result

    def test_date_add_is_not_a_field_reference(self):
        result = extract_formula_fields("dateOrder < date_add(now(), 30)")
        assert "dateOrder" in result
        assert "date_add" not in result
        assert "now" not in result

    def test_date_sub_is_not_a_field_reference(self):
        result = extract_formula_fields("dateOrder > date_sub(now(), 7)")
        assert "dateOrder" in result
        assert "date_sub" not in result
        assert "now" not in result

    def test_datetime_is_not_a_field_reference(self):
        result = extract_formula_fields("createdAt < datetime()")
        assert "createdAt" in result
        assert "datetime" not in result
