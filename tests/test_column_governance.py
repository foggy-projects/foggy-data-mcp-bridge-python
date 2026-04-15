"""Tests for v1.3 column governance — field_validator + masking.

Covers:
- Expression parsing & field extraction
- Dependency-aware field extraction from inline expressions
- Alias back-tracking for orderBy (including expression aliases)
- Visible-field validation (columns, slice, orderBy, calculatedFields)
- Result column filtering
- Masking execution (full_mask, partial_mask, email_mask, phone_mask)
- Backward compatibility (None field_access)
"""

import pytest

from foggy.mcp_spi.semantic import FieldAccessDef, SystemSlice, SemanticQueryRequest
from foggy.dataset_model.semantic.field_validator import (
    extract_field_dependencies,
    _extract_field_dependencies,
    _parse_column_expr,
    validate_field_access,
    filter_response_columns,
    FieldValidationResult,
    _extract_fields_from_slice,
)
from foggy.dataset_model.semantic.masking import (
    apply_masking,
    _mask_full,
    _mask_partial,
    _mask_email,
    _mask_phone,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model


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

class TestParseColumnExpr:
    """Test expression parsing, field extraction, and dependency resolution."""

    def test_bare_field(self):
        p = _parse_column_expr("name")
        assert p.source_field == "name"
        assert p.source_fields == {"name"}
        assert p.alias is None

    def test_dimension_caption(self):
        p = _parse_column_expr("partner$caption")
        assert p.source_field == "partner$caption"
        assert p.source_fields == {"partner$caption"}

    def test_dimension_id(self):
        p = _parse_column_expr("partner$id")
        assert p.source_field == "partner$id"

    def test_dimension_property(self):
        p = _parse_column_expr("company$industry")
        assert p.source_field == "company$industry"

    def test_sum_with_alias(self):
        p = _parse_column_expr("sum(amountTotal) as total")
        assert p.source_field == "amountTotal"
        assert p.source_fields == {"amountTotal"}
        assert p.alias == "total"

    def test_count_with_alias(self):
        p = _parse_column_expr("count(name) as cnt")
        assert p.source_field == "name"
        assert p.alias == "cnt"

    def test_avg_with_alias(self):
        p = _parse_column_expr("avg(price) as avgPrice")
        assert p.source_field == "price"

    def test_min_no_alias(self):
        p = _parse_column_expr("min(amount)")
        assert p.source_field == "amount"
        assert p.source_fields == {"amount"}

    def test_max_no_alias(self):
        p = _parse_column_expr("max(quantity)")
        assert p.source_field == "quantity"

    def test_field_as_alias_no_agg(self):
        p = _parse_column_expr("amountTotal as amt")
        assert p.source_field == "amountTotal"
        assert p.alias == "amt"

    def test_count_distinct(self):
        p = _parse_column_expr("count_distinct(customerId) as uniqueCustomers")
        assert p.source_field == "customerId"

    def test_whitespace_tolerance(self):
        p = _parse_column_expr("  sum( amountTotal ) as total  ")
        assert p.source_field == "amountTotal"

    def test_arithmetic_expression_with_alias(self):
        p = _parse_column_expr("a + b as c")
        assert p.alias == "c"
        assert p.source_fields == {"a", "b"}

    def test_agg_over_expression_with_alias(self):
        p = _parse_column_expr("sum(a + b) as total")
        assert p.alias == "total"
        assert p.source_fields == {"a", "b"}


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


# ============================================================================
# BUG FIX: display_name → qm_field_name mapping
# ============================================================================

class TestFilterResponseColumnsWithDisplayNames:
    """Regression tests for display-name mismatch bug.

    Engine returns items with display-name keys (SQL aliases like "Email"),
    but field_access.visible uses QM field names (like "email").
    The display_to_qm mapping bridges the gap.
    """

    def test_display_name_filtering(self):
        """Items keyed by display name should be filtered using qm mapping."""
        fa = FieldAccessDef(visible=["name", "email"])
        display_to_qm = {"Name": "name", "Email": "email", "Secret": "secret"}
        rows = [{"Name": "Admin", "Email": "a@b.com", "Secret": "password"}]
        result = filter_response_columns(rows, fa, display_to_qm=display_to_qm)
        assert result == [{"Name": "Admin", "Email": "a@b.com"}]

    def test_display_name_no_mapping_fallback(self):
        """Without display_to_qm, keys are matched directly (legacy compat)."""
        fa = FieldAccessDef(visible=["name", "email"])
        rows = [{"name": "Admin", "email": "a@b.com", "secret": "x"}]
        result = filter_response_columns(rows, fa, display_to_qm=None)
        assert result == [{"name": "Admin", "email": "a@b.com"}]

    def test_display_name_all_blocked(self):
        """If all display-name keys map to blocked qm fields, result is empty dicts."""
        fa = FieldAccessDef(visible=["name"])
        display_to_qm = {"Secret": "secret", "Hidden": "hidden"}
        rows = [{"Secret": "x", "Hidden": "y"}]
        result = filter_response_columns(rows, fa, display_to_qm=display_to_qm)
        assert result == [{}]

    def test_display_name_partial_mapping(self):
        """Keys not in display_to_qm fall back to direct match."""
        fa = FieldAccessDef(visible=["name", "rawKey"])
        display_to_qm = {"Name": "name"}  # rawKey not in mapping
        rows = [{"Name": "Admin", "rawKey": "value", "Other": "x"}]
        result = filter_response_columns(rows, fa, display_to_qm=display_to_qm)
        assert result == [{"Name": "Admin", "rawKey": "value"}]


class TestApplyMaskingWithDisplayNames:
    """Regression tests for masking with display-name mismatch."""

    def test_masking_via_display_name(self):
        """Masking rules use QM names, but row keys are display names."""
        fa = FieldAccessDef(masking={"email": "email_mask", "phone": "phone_mask"})
        display_to_qm = {"Name": "name", "Email": "email", "Phone": "phone"}
        rows = [{"Name": "Zhang", "Email": "zhang@test.com", "Phone": "13812345678"}]
        apply_masking(rows, fa, display_to_qm=display_to_qm)
        assert rows[0]["Name"] == "Zhang"  # unmasked
        assert rows[0]["Email"] == "z***@test.com"
        assert rows[0]["Phone"] == "138****5678"

    def test_masking_no_mapping_fallback(self):
        """Without display_to_qm, keys are matched directly (legacy compat)."""
        fa = FieldAccessDef(masking={"email": "email_mask"})
        rows = [{"email": "a@b.com"}]
        apply_masking(rows, fa, display_to_qm=None)
        assert rows[0]["email"] == "a***@b.com"

    def test_masking_display_name_full_mask(self):
        fa = FieldAccessDef(masking={"secret": "full_mask"})
        display_to_qm = {"Secret Field": "secret"}
        rows = [{"Secret Field": "password123", "Name": "test"}]
        apply_masking(rows, fa, display_to_qm=display_to_qm)
        assert rows[0]["Secret Field"] == "***"
        assert rows[0]["Name"] == "test"

    def test_combined_filter_then_mask(self):
        """End-to-end: filter visible columns, then mask remaining."""
        fa = FieldAccessDef(
            visible=["name", "email"],
            masking={"email": "email_mask"},
        )
        display_to_qm = {"Name": "name", "Email": "email", "Secret": "secret"}
        rows = [{"Name": "Admin", "Email": "admin@example.com", "Secret": "pwd"}]

        # Step 1: filter
        filtered = filter_response_columns(rows, fa, display_to_qm=display_to_qm)
        assert filtered == [{"Name": "Admin", "Email": "admin@example.com"}]

        # Step 2: mask
        apply_masking(filtered, fa, display_to_qm=display_to_qm)
        assert filtered[0]["Name"] == "Admin"
        assert filtered[0]["Email"] == "a***@example.com"


# ============================================================================
# Service-level governance verification for calculated / expression fields
# ============================================================================


@pytest.fixture
def sales_service():
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    return svc


class TestServiceLevelCalculatedFieldGovernance:
    """Verify actual query_model behavior, not just validator helpers."""

    def test_calculated_fields_rejects_blocked_source_field(self, sales_service):
        req = SemanticQueryRequest(
            columns=["orderStatus"],
            calculated_fields=[{
                "name": "netAmount",
                "expression": "salesAmount + discountAmount",
            }],
            field_access=FieldAccessDef(visible=["orderStatus", "salesAmount"]),
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is not None
        assert "discountAmount" in result.error

    # --- v1.3 dependency-aware inline expression tests ---

    def test_inline_arithmetic_expression_rejects_blocked_dependency(self, sales_service):
        """`a + b as c`: when b is blocked, error names b specifically."""
        req = SemanticQueryRequest(
            columns=["salesAmount + discountAmount as totalAmount"],
            field_access=FieldAccessDef(visible=["salesAmount"]),  # discountAmount blocked
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is not None
        assert "discountAmount" in result.error
        # Should report the specific blocked field, not the whole expression
        assert "salesAmount + discountAmount" not in result.error

    def test_inline_aggregate_expression_rejects_blocked_dependency(self, sales_service):
        """`sum(a + b) as total`: when b is blocked, error names b."""
        req = SemanticQueryRequest(
            columns=["sum(salesAmount + discountAmount) as totalAmount"],
            field_access=FieldAccessDef(visible=["salesAmount"]),  # discountAmount blocked
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is not None
        assert "discountAmount" in result.error

    def test_inline_arithmetic_all_visible_passes(self, sales_service):
        """`a + b as c`: when both a and b are visible, query passes."""
        req = SemanticQueryRequest(
            columns=["salesAmount + discountAmount as totalAmount"],
            field_access=FieldAccessDef(visible=["salesAmount", "discountAmount"]),
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is None

    def test_inline_aggregate_all_visible_passes(self, sales_service):
        """`sum(a + b) as total`: when both a and b are visible, query passes."""
        req = SemanticQueryRequest(
            columns=["sum(salesAmount + discountAmount) as totalAmount"],
            field_access=FieldAccessDef(visible=["salesAmount", "discountAmount"]),
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is None

    # --- orderBy alias back-tracking to expression dependencies ---

    def test_orderby_alias_backtrack_to_expression_blocked(self, sales_service):
        """orderBy alias → expression deps: blocked dep is reported."""
        req = SemanticQueryRequest(
            columns=["salesAmount + discountAmount as total"],
            order_by=[{"field": "total", "dir": "desc"}],
            field_access=FieldAccessDef(visible=["salesAmount"]),  # discountAmount blocked
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is not None
        assert "discountAmount" in result.error

    def test_orderby_alias_backtrack_to_expression_passes(self, sales_service):
        """orderBy alias → expression deps: all visible passes."""
        req = SemanticQueryRequest(
            columns=["salesAmount + discountAmount as total"],
            order_by=[{"field": "total", "dir": "desc"}],
            field_access=FieldAccessDef(visible=["salesAmount", "discountAmount"]),
        )

        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is None

    # --- accessor payload full-chain integration test ---

    def test_accessor_payload_expression_rejection(self, sales_service):
        """Full chain: JSON payload → build_query_request → query_model → rejection."""
        from foggy.mcp_spi.accessor import build_query_request
        payload = {
            "columns": ["orderStatus", "salesAmount + discountAmount as total"],
            "slice": [],
            "orderBy": [{"field": "total", "dir": "desc"}],
            "fieldAccess": {"visible": ["orderStatus", "salesAmount"]},
        }
        req = build_query_request(payload)
        result = sales_service.query_model("FactSalesModel", req, mode="validate")

        assert result.error is not None
        assert "discountAmount" in result.error

    # --- fail-closed for unparseable expressions ---

    def test_unparseable_expression_fails_closed(self):
        """Expression with no extractable fields should fail closed."""
        fa = FieldAccessDef(visible=["name"])
        result = validate_field_access(
            columns=["name", "1 + 2 as computed"],
            slice_items=[],
            order_by=[],
            field_access=fa,
        )
        # "1 + 2" has no field dependencies — the whole expression
        # is not in visible set, so it should be rejected (fail-closed)
        assert not result.valid


# ============================================================================
# Dependency extraction unit tests
# ============================================================================

class TestExtractFieldDependencies:
    """Test _extract_field_dependencies() shared primitive."""

    def test_bare_field(self):
        assert _extract_field_dependencies("name") == {"name"}

    def test_dimension_accessor(self):
        assert _extract_field_dependencies("partner$caption") == {"partner$caption"}

    def test_arithmetic(self):
        assert _extract_field_dependencies("a + b") == {"a", "b"}

    def test_multiply(self):
        assert _extract_field_dependencies("unitPrice * quantity") == {"unitPrice", "quantity"}

    def test_case_when(self):
        deps = _extract_field_dependencies("case when status = 1 then amount else 0 end")
        assert "status" in deps
        assert "amount" in deps
        assert "case" not in deps
        assert "when" not in deps

    def test_agg_wrapper(self):
        assert _extract_field_dependencies("sum(a + b)") == {"a", "b"}

    def test_string_literal_stripped(self):
        deps = _extract_field_dependencies("case when name = 'active' then 1 end")
        assert "name" in deps
        assert "active" not in deps

    def test_no_fields(self):
        assert _extract_field_dependencies("1 + 2") == set()

    def test_empty(self):
        assert _extract_field_dependencies("") == set()

    def test_nested_function(self):
        deps = _extract_field_dependencies("round(a / b, 2)")
        assert "a" in deps
        assert "b" in deps
        assert "round" not in deps


class TestExtractFieldDependenciesPublic:
    """Test the public extract_field_dependencies() API."""

    def test_bare_field(self):
        assert extract_field_dependencies("name") == {"name"}

    def test_arithmetic_with_alias(self):
        deps = extract_field_dependencies("a + b as c")
        assert deps == {"a", "b"}

    def test_agg_over_expression_with_alias(self):
        deps = extract_field_dependencies("sum(a + b) as total")
        assert deps == {"a", "b"}

    def test_simple_agg(self):
        deps = extract_field_dependencies("sum(amount) as total")
        assert deps == {"amount"}
