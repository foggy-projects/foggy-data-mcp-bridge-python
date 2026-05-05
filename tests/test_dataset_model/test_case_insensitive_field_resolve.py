"""Tests for case-insensitive canonical field resolution.

Verifies that the engine resolves field names that differ only by case
from the canonical schema name before validation, permission checks,
and SQL generation. Also verifies fail-closed ambiguity detection and
feature-flag toggleability.
"""

import pytest

from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest
from foggy.demo.models.ecommerce_models import create_fact_sales_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service():
    """Create a SemanticQueryService with the FactSalesModel registered."""
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    return svc


@pytest.fixture
def service_ci_disabled():
    """Service with case-insensitive resolution explicitly disabled."""
    svc = SemanticQueryService(auto_case_insensitive_field_resolve=False)
    svc.register_model(create_fact_sales_model())
    return svc


def _build_sql(service: SemanticQueryService, request: SemanticQueryRequest) -> str:
    """Helper: build SQL via validate mode and return the SQL string."""
    response = service.query_model("FactSalesModel", request, mode="validate")
    assert response.error is None, f"Unexpected error: {response.error}"
    assert response.sql is not None, "Expected SQL in response"
    return response.sql


# ---------------------------------------------------------------------------
# Core resolution tests
# ---------------------------------------------------------------------------


class TestCaseInsensitiveFieldResolve:
    """Verify that case-only variants resolve to canonical field names."""

    def test_columns_case_variant_resolves_to_canonical(self, service):
        """'salesamount' (all-lower) should resolve to canonical 'salesAmount'."""
        request = SemanticQueryRequest(columns=["salesamount"])
        sql = _build_sql(service, request)
        # The generated SQL should reference the physical column mapped
        # to the canonical 'salesAmount'.
        assert "sales_amount" in sql.lower(), (
            f"Expected physical column for salesAmount in SQL: {sql}"
        )

    def test_columns_upper_case_variant_resolves(self, service):
        """'SALESAMOUNT' should resolve to canonical 'salesAmount'."""
        request = SemanticQueryRequest(columns=["SALESAMOUNT"])
        sql = _build_sql(service, request)
        assert "sales_amount" in sql.lower()

    def test_mixed_case_columns_all_resolve(self, service):
        """Mix of canonical and case-variant columns all resolve."""
        request = SemanticQueryRequest(
            columns=["salesAmount", "QUANTITY", "profitamount"]
        )
        sql = _build_sql(service, request)
        assert "sales_amount" in sql.lower()
        assert "quantity" in sql.lower()
        assert "profit_amount" in sql.lower() or "profit" in sql.lower()

    def test_exact_match_preferred(self, service):
        """Exact-casing match short-circuits case-insensitive lookup."""
        request = SemanticQueryRequest(columns=["salesAmount"])
        sql = _build_sql(service, request)
        assert "sales_amount" in sql.lower()

    def test_slice_case_variant_resolves(self, service):
        """Slice field references with wrong casing should resolve."""
        request = SemanticQueryRequest(
            columns=["salesDate$caption", "salesAmount"],
            slice=[{"field": "salesdate$caption", "op": "=", "value": "2024-01-01"}],
        )
        sql = _build_sql(service, request)
        # The WHERE clause should contain the physical column for salesDate
        assert "WHERE" in sql.upper() or "sales_date" in sql.lower()

    def test_orderby_case_variant_resolves(self, service):
        """Order-by with case variant field name should resolve."""
        request = SemanticQueryRequest(
            columns=["salesAmount"],
            order_by=["-salesamount"],
        )
        sql = _build_sql(service, request)
        assert "ORDER BY" in sql.upper()
        assert "sales_amount" in sql.lower()

    def test_groupby_case_variant_resolves(self, service):
        """Group-by case variant should resolve to canonical dimension."""
        request = SemanticQueryRequest(
            columns=["salesDate$caption", "salesAmount"],
            group_by=["SALESDATE$CAPTION"],
        )
        sql = _build_sql(service, request)
        assert "GROUP BY" in sql.upper()

    def test_having_case_variant_resolves(self, service):
        """Having filter with case variant measure should resolve."""
        request = SemanticQueryRequest(
            columns=["salesDate$caption", "salesAmount"],
            group_by=["salesDate$caption"],
            having=[{"field": "SALESAMOUNT", "op": ">", "value": 0}],
        )
        sql = _build_sql(service, request)
        assert "HAVING" in sql.upper()

    def test_aggregate_slice_lift_with_case_variant(self, service):
        """Aggregate measure in slice with case variant should still auto-lift to HAVING."""
        request = SemanticQueryRequest(
            columns=["salesDate$caption", "salesAmount"],
            slice=[{"field": "salesamount", "op": ">", "value": 0}],
        )
        sql = _build_sql(service, request)
        assert "HAVING" in sql.upper()


# ---------------------------------------------------------------------------
# Explicit alias / snake_case must NOT resolve
# ---------------------------------------------------------------------------


class TestNoSnakeCaseConversion:
    """Verify that only case-only variants are resolved; snake_case is NOT."""

    def test_snake_case_not_resolved(self, service):
        """'sales_amount' must NOT resolve to 'salesAmount' — these
        differ in structure, not just casing."""
        request = SemanticQueryRequest(columns=["sales_amount"])
        response = service.query_model("FactSalesModel", request, mode="validate")
        # Should trigger an unknown-field error (or at least not succeed
        # with the canonical salesAmount's physical column)
        assert response.error is not None, (
            "snake_case field should not be resolved via case-insensitive lookup"
        )


# ---------------------------------------------------------------------------
# Ambiguity detection (fail-closed)
# ---------------------------------------------------------------------------


class TestAmbiguousFieldDetection:
    """Verify fail-closed behavior when the schema has case-collision fields."""

    def test_ambiguous_case_fields_fail_closed(self):
        """Schema with both 'amount' and 'Amount' — referencing 'AMOUNT'
        should produce CASE_INSENSITIVE_FIELD_AMBIGUOUS error."""
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
            CaseInsensitiveFieldAmbiguousError,
        )

        resolver = CaseInsensitiveFieldResolver({"amount", "Amount"})

        # Exact matches should still work
        assert resolver.resolve("amount") == "amount"
        assert resolver.resolve("Amount") == "Amount"

        # Ambiguous case variant should fail
        with pytest.raises(CaseInsensitiveFieldAmbiguousError) as exc_info:
            resolver.resolve("AMOUNT")
        assert exc_info.value.error_code == "CASE_INSENSITIVE_FIELD_AMBIGUOUS"
        assert set(exc_info.value.candidates) == {"Amount", "amount"}


# ---------------------------------------------------------------------------
# Feature flag toggle
# ---------------------------------------------------------------------------


class TestFeatureFlagDisabled:
    """Verify that disabling the feature flag preserves exact-match-only behavior."""

    def test_case_variant_rejected_when_flag_disabled(self, service_ci_disabled):
        """With the feature disabled, 'salesamount' should not resolve
        and should fail as an unknown field."""
        request = SemanticQueryRequest(columns=["salesamount"])
        response = service_ci_disabled.query_model(
            "FactSalesModel", request, mode="validate"
        )
        assert response.error is not None, (
            "Case variant should not resolve when feature flag is disabled"
        )


# ---------------------------------------------------------------------------
# Unit tests for the resolver itself
# ---------------------------------------------------------------------------


class TestCaseInsensitiveFieldResolverUnit:
    """Low-level unit tests for the resolver utility."""

    def test_resolve_exact_match(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount", "salesAmount"})
        assert resolver.resolve("arOverdueAmount") == "arOverdueAmount"
        assert resolver.resolve("salesAmount") == "salesAmount"

    def test_resolve_case_variant(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount", "salesAmount"})
        assert resolver.resolve("aroverdueamount") == "arOverdueAmount"
        assert resolver.resolve("AROVERDUEAMOUNT") == "arOverdueAmount"
        assert resolver.resolve("ArOverdueAmount") == "arOverdueAmount"
        assert resolver.resolve("SALESAMOUNT") == "salesAmount"

    def test_resolve_no_match_returns_unchanged(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount"})
        assert resolver.resolve("nonExistentField") == "nonExistentField"

    def test_resolve_or_none_returns_none(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount"})
        assert resolver.resolve_or_none("nonExistentField") is None

    def test_resolve_snake_case_not_matched(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"arOverdueAmount"})
        # snake_case has different characters (underscores) — not a case variant
        assert resolver.resolve("ar_overdue_amount") == "ar_overdue_amount"

    def test_resolve_dimension_suffix_preserved(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            CaseInsensitiveFieldResolver,
        )
        resolver = CaseInsensitiveFieldResolver({"orderStatus$caption", "orderStatus$id"})
        assert resolver.resolve("orderstatus$caption") == "orderStatus$caption"
        assert resolver.resolve("ORDERSTATUS$ID") == "orderStatus$id"

    def test_feature_flag_enabled_by_default(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            case_insensitive_field_resolve_enabled,
        )
        assert case_insensitive_field_resolve_enabled() is True

    def test_feature_flag_constructor_override(self):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            case_insensitive_field_resolve_enabled,
        )
        assert case_insensitive_field_resolve_enabled(False) is False
        assert case_insensitive_field_resolve_enabled(True) is True

    def test_feature_flag_env_override(self, monkeypatch):
        from foggy.dataset_model.semantic.case_insensitive_resolver import (
            case_insensitive_field_resolve_enabled,
        )
        monkeypatch.setenv("FOGGY_DATASET_CASE_INSENSITIVE_FIELD_RESOLVE", "false")
        assert case_insensitive_field_resolve_enabled() is False
        monkeypatch.setenv("FOGGY_DATASET_CASE_INSENSITIVE_FIELD_RESOLVE", "true")
        assert case_insensitive_field_resolve_enabled() is True
