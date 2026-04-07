"""Tests for v1.2 column governance — field_validator + masking.

Covers:
- Expression parsing & field extraction
- Alias back-tracking for orderBy
- Visible-field validation (columns, slice, orderBy, calculatedFields)
- Result column filtering
- Masking execution (full_mask, partial_mask, email_mask, phone_mask)
- Backward compatibility (None field_access)
"""

import pytest

from foggy.mcp_spi.semantic import FieldAccessDef, SystemSlice, SemanticQueryRequest
from foggy.dataset_model.semantic.field_validator import (
    extract_field_from_expr,
    validate_field_access,
    filter_response_columns,
    FieldValidationResult,
    _build_alias_map,
    _extract_fields_from_slice,
)
from foggy.dataset_model.semantic.masking import (
    apply_masking,
    _mask_full,
    _mask_partial,
    _mask_email,
    _mask_phone,
)


# ============================================================================
# FieldAccessDef / SystemSlice DTO tests
# ============================================================================

class TestFieldAccessDef:
    def test_default_empty(self):
        fa = FieldAccessDef()
        assert fa.visible == []
        assert fa.masking == {}

    def test_with_values(self):
        fa = FieldAccessDef(visible=["name", "amount"], masking={"email": "email_mask"})
        assert fa.visible == ["name", "amount"]
        assert fa.masking == {"email": "email_mask"}

    def test_json_round_trip(self):
        fa = FieldAccessDef(visible=["name"], masking={"phone": "phone_mask"})
        d = fa.model_dump(by_alias=True)
        fa2 = FieldAccessDef(**d)
        assert fa2.visible == fa.visible
        assert fa2.masking == fa.masking


class TestSystemSlice:
    def test_default_empty(self):
        ss = SystemSlice()
        assert ss.slices == []

    def test_with_slices(self):
        ss = SystemSlice(slices=[{"field": "company_id", "op": "eq", "value": 1}])
        assert len(ss.slices) == 1


class TestSemanticQueryRequestGovernance:
    def test_backward_compat_no_governance(self):
        req = SemanticQueryRequest(columns=["name"])
        assert req.field_access is None
        assert req.system_slice is None

    def test_with_governance(self):
        fa = FieldAccessDef(visible=["name", "amount"])
        req = SemanticQueryRequest(
            columns=["name"],
            field_access=fa,
            system_slice=[{"field": "x", "op": "eq", "value": 1}],
        )
        assert req.field_access is not None
        assert req.field_access.visible == ["name", "amount"]
        assert len(req.system_slice) == 1

    def test_json_alias(self):
        req = SemanticQueryRequest(
            columns=["name"],
            field_access=FieldAccessDef(visible=["name"]),
            system_slice=[{"field": "x"}],
        )
        d = req.model_dump(by_alias=True, exclude_none=True)
        assert "fieldAccess" in d
        assert "systemSlice" in d


# ============================================================================
# Expression parsing tests
# ============================================================================

class TestExtractFieldFromExpr:
    """Test expression parsing and field extraction."""

    def test_bare_field(self):
        assert extract_field_from_expr("name") == "name"

    def test_dimension_caption(self):
        assert extract_field_from_expr("partner$caption") == "partner$caption"

    def test_dimension_id(self):
        assert extract_field_from_expr("partner$id") == "partner$id"

    def test_dimension_property(self):
        assert extract_field_from_expr("company$industry") == "company$industry"

    def test_sum_with_alias(self):
        assert extract_field_from_expr("sum(amountTotal) as total") == "amountTotal"

    def test_count_with_alias(self):
        assert extract_field_from_expr("count(name) as cnt") == "name"

    def test_avg_with_alias(self):
        assert extract_field_from_expr("avg(price) as avgPrice") == "price"

    def test_min_no_alias(self):
        assert extract_field_from_expr("min(amount)") == "amount"

    def test_max_no_alias(self):
        assert extract_field_from_expr("max(quantity)") == "quantity"

    def test_field_as_alias_no_agg(self):
        assert extract_field_from_expr("amountTotal as amt") == "amountTotal"

    def test_count_distinct(self):
        assert extract_field_from_expr("count_distinct(customerId) as uniqueCustomers") == "customerId"

    def test_whitespace_tolerance(self):
        assert extract_field_from_expr("  sum( amountTotal ) as total  ") == "amountTotal"


# ============================================================================
# Alias map tests
# ============================================================================

class TestBuildAliasMap:
    def test_basic(self):
        m = _build_alias_map(["name", "sum(amount) as total", "count(name) as cnt"])
        assert m == {"total": "amount", "cnt": "name"}

    def test_no_aliases(self):
        m = _build_alias_map(["name", "partner$caption"])
        assert m == {}

    def test_field_as_alias(self):
        m = _build_alias_map(["amountTotal as amt"])
        assert m == {"amt": "amountTotal"}


# ============================================================================
# Slice field extraction tests
# ============================================================================

class TestExtractFieldsFromSlice:
    def test_simple(self):
        fields = _extract_fields_from_slice([
            {"field": "name", "op": "eq", "value": "test"},
            {"field": "amount", "op": "gt", "value": 100},
        ])
        assert fields == {"name", "amount"}

    def test_nested(self):
        fields = _extract_fields_from_slice([{
            "logic": "and",
            "conditions": [
                {"field": "name", "op": "eq", "value": "a"},
                {"field": "status", "op": "eq", "value": "active"},
            ]
        }])
        assert "name" in fields
        assert "status" in fields

    def test_empty(self):
        assert _extract_fields_from_slice([]) == set()
        assert _extract_fields_from_slice(None) == set()


# ============================================================================
# Field validation tests
# ============================================================================

class TestValidateFieldAccess:
    """Test the main validation function."""

    def test_no_governance_always_passes(self):
        result = validate_field_access(
            columns=["anything", "blocked_secret"],
            slice_items=[{"field": "whatever"}],
            order_by=[{"field": "x"}],
            field_access=None,
        )
        assert result.valid

    def test_empty_visible_passes(self):
        """Empty visible list = no governance (v1.1 compat)."""
        fa = FieldAccessDef(visible=[])
        result = validate_field_access(
            columns=["anything"],
            slice_items=[],
            order_by=[],
            field_access=fa,
        )
        assert result.valid

    def test_all_visible_passes(self):
        fa = FieldAccessDef(visible=["name", "amount", "partner$caption"])
        result = validate_field_access(
            columns=["name", "sum(amount) as total"],
            slice_items=[{"field": "name", "op": "eq", "value": "test"}],
            order_by=[{"field": "total"}],  # alias → amount → visible
            field_access=fa,
        )
        assert result.valid

    def test_blocked_in_columns(self):
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["name", "secretField"],
            slice_items=[],
            order_by=[],
            field_access=fa,
        )
        assert not result.valid
        assert "secretField" in result.blocked_fields
        assert "not accessible" in result.error_message

    def test_blocked_in_slice(self):
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["name"],
            slice_items=[{"field": "blocked_field", "op": "eq", "value": "x"}],
            order_by=[],
            field_access=fa,
        )
        assert not result.valid
        assert "blocked_field" in result.blocked_fields

    def test_blocked_in_orderby(self):
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["name"],
            slice_items=[],
            order_by=[{"field": "blocked_field", "dir": "asc"}],
            field_access=fa,
        )
        assert not result.valid
        assert "blocked_field" in result.blocked_fields

    def test_orderby_alias_backtrack(self):
        """orderBy referencing alias should back-track to source field."""
        fa = FieldAccessDef(visible=["name", "amount"])
        result = validate_field_access(
            columns=["name", "sum(amount) as total"],
            slice_items=[],
            order_by=[{"field": "total", "dir": "desc"}],
            field_access=fa,
        )
        assert result.valid  # "total" → "amount" → visible

    def test_orderby_alias_backtrack_blocked(self):
        fa = FieldAccessDef(visible=["name"])  # "amount" is blocked
        result = validate_field_access(
            columns=["name", "sum(amount) as total"],  # "amount" blocked
            slice_items=[],
            order_by=[{"field": "total"}],
            field_access=fa,
        )
        assert not result.valid
        assert "amount" in result.blocked_fields

    def test_aggregation_extracts_source(self):
        """sum(amountTotal) should check amountTotal, not the expression."""
        fa = FieldAccessDef(visible=["amountTotal"])
        result = validate_field_access(
            columns=["sum(amountTotal) as total"],
            slice_items=[],
            order_by=[],
            field_access=fa,
        )
        assert result.valid

    def test_dimension_field_visible(self):
        fa = FieldAccessDef(visible=["partner$id", "partner$caption"])
        result = validate_field_access(
            columns=["partner$id", "partner$caption"],
            slice_items=[],
            order_by=[],
            field_access=fa,
        )
        assert result.valid

    def test_deduplicate_blocked(self):
        """Same blocked field in multiple places should be deduped."""
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["secretField"],
            slice_items=[{"field": "secretField"}],
            order_by=[{"field": "secretField"}],
            field_access=fa,
        )
        assert not result.valid
        assert result.blocked_fields == ["secretField"]  # deduped

    def test_calculated_fields_validation(self):
        fa = FieldAccessDef(visible=["name", "amount"])
        result = validate_field_access(
            columns=["name"],
            slice_items=[],
            order_by=[],
            calculated_fields=[{"expression": "amount * 1.1", "alias": "taxed"}],
            field_access=fa,
        )
        assert result.valid

    def test_calculated_fields_blocked(self):
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["name"],
            slice_items=[],
            order_by=[],
            calculated_fields=[{"expression": "secretField * 2", "alias": "doubled"}],
            field_access=fa,
        )
        assert not result.valid
        assert "secretField" in result.blocked_fields


# ============================================================================
# Result column filtering tests
# ============================================================================

class TestFilterResponseColumns:
    def test_no_governance(self):
        rows = [{"name": "a", "secret": "x"}]
        result = filter_response_columns(rows, None)
        assert result == rows

    def test_empty_visible(self):
        fa = FieldAccessDef(visible=[])
        rows = [{"name": "a", "secret": "x"}]
        result = filter_response_columns(rows, fa)
        assert result == rows  # empty visible = no filtering

    def test_filters_blocked(self):
        fa = FieldAccessDef(visible=["name", "amount"])
        rows = [{"name": "a", "amount": 100, "secret": "x"}]
        result = filter_response_columns(rows, fa)
        assert result == [{"name": "a", "amount": 100}]

    def test_empty_rows(self):
        fa = FieldAccessDef(visible=["name"])
        assert filter_response_columns([], fa) == []


# ============================================================================
# Masking tests
# ============================================================================

class TestMaskFunctions:
    """Test individual mask functions."""

    def test_full_mask(self):
        assert _mask_full("anything") == "***"
        assert _mask_full(None) == "***"
        assert _mask_full(123) == "***"

    def test_partial_mask(self):
        assert _mask_partial("张三丰") == "张**"
        assert _mask_partial("Alice") == "A****"
        assert _mask_partial("A") == "***"  # too short
        assert _mask_partial("") == "***"
        assert _mask_partial(None) == "***"

    def test_email_mask(self):
        assert _mask_email("zhang@example.com") == "z***@example.com"
        assert _mask_email("a@b.com") == "a***@b.com"
        assert _mask_email("not-an-email") == "***"
        assert _mask_email(None) == "***"

    def test_phone_mask(self):
        assert _mask_phone("13812345678") == "138****5678"
        assert _mask_phone("021-12345678") == "021****5678"
        assert _mask_phone("12345") == "1****"  # fallback to partial
        assert _mask_phone(None) == "***"


class TestApplyMasking:
    """Test the apply_masking function."""

    def test_no_governance(self):
        rows = [{"name": "test", "email": "a@b.com"}]
        result = apply_masking(rows, None)
        assert result[0]["email"] == "a@b.com"

    def test_no_masking_rules(self):
        fa = FieldAccessDef(visible=["name", "email"])
        rows = [{"name": "test", "email": "a@b.com"}]
        result = apply_masking(rows, fa)
        assert result[0]["email"] == "a@b.com"

    def test_email_masking(self):
        fa = FieldAccessDef(visible=["name", "email"], masking={"email": "email_mask"})
        rows = [{"name": "Zhang", "email": "zhang@test.com"}]
        result = apply_masking(rows, fa)
        assert result[0]["name"] == "Zhang"  # unmasked
        assert result[0]["email"] == "z***@test.com"

    def test_phone_masking(self):
        fa = FieldAccessDef(masking={"phone": "phone_mask"})
        rows = [{"phone": "13812345678"}]
        result = apply_masking(rows, fa)
        assert result[0]["phone"] == "138****5678"

    def test_full_masking(self):
        fa = FieldAccessDef(masking={"secret": "full_mask"})
        rows = [{"secret": "confidential"}]
        result = apply_masking(rows, fa)
        assert result[0]["secret"] == "***"

    def test_partial_masking(self):
        fa = FieldAccessDef(masking={"name": "partial_mask"})
        rows = [{"name": "张三丰"}]
        result = apply_masking(rows, fa)
        assert result[0]["name"] == "张**"

    def test_unknown_mask_type_falls_back_to_full(self):
        fa = FieldAccessDef(masking={"field": "unknown_type"})
        rows = [{"field": "value"}]
        result = apply_masking(rows, fa)
        assert result[0]["field"] == "***"

    def test_multiple_fields(self):
        fa = FieldAccessDef(masking={
            "email": "email_mask",
            "phone": "phone_mask",
            "name": "partial_mask",
        })
        rows = [{"email": "a@b.com", "phone": "13800001234", "name": "Alice", "id": 1}]
        result = apply_masking(rows, fa)
        assert result[0]["email"] == "a***@b.com"
        assert result[0]["phone"] == "138****1234"
        assert result[0]["name"] == "A****"
        assert result[0]["id"] == 1  # unmasked

    def test_empty_rows(self):
        fa = FieldAccessDef(masking={"field": "full_mask"})
        assert apply_masking([], fa) == []

    def test_masking_missing_field(self):
        """If masking rule references a field not in the row, skip it."""
        fa = FieldAccessDef(masking={"missing_field": "full_mask"})
        rows = [{"name": "test"}]
        result = apply_masking(rows, fa)
        assert result[0] == {"name": "test"}


# ============================================================================
# Integration: build_query_request with governance params
# ============================================================================

class TestBuildQueryRequestGovernance:
    def test_no_governance_in_payload(self):
        from foggy.mcp_spi.accessor import build_query_request
        req = build_query_request({"columns": ["name"], "slice": []})
        assert req.field_access is None
        assert req.system_slice is None

    def test_with_governance_in_payload(self):
        from foggy.mcp_spi.accessor import build_query_request
        req = build_query_request({
            "columns": ["name"],
            "slice": [],
            "fieldAccess": {"visible": ["name", "amount"], "masking": {"email": "email_mask"}},
            "systemSlice": [{"field": "company_id", "op": "eq", "value": 1}],
        })
        assert req.field_access is not None
        assert req.field_access.visible == ["name", "amount"]
        assert req.field_access.masking == {"email": "email_mask"}
        assert req.system_slice == [{"field": "company_id", "op": "eq", "value": 1}]
