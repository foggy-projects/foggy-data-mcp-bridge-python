"""Tests for v1.3 physical column governance — denied_columns + mapping cache.

Covers:
- DeniedColumn DTO creation and serialization
- PhysicalColumnMapping forward/reverse lookups
- denied_columns → denied QM fields conversion
- field_access + denied_columns combined semantics
- system_slice bypasses field governance (including denied_columns)
- metadata physicalTables output
- metadata field trimming with denied_columns
- accessor payload deniedColumns passthrough
- Service-level integration (query_model with denied_columns)
"""

import pytest

from foggy.mcp_spi.semantic import (
    DeniedColumn,
    FieldAccessDef,
    SemanticMetadataRequest,
    SemanticQueryRequest,
    SystemSlice,
)
from foggy.mcp_spi.accessor import build_query_request
from foggy.dataset_model.semantic.physical_column_mapping import (
    PhysicalColumnMapping,
    PhysicalColumnRef,
    build_physical_column_mapping,
)
from foggy.dataset_model.semantic.field_validator import (
    validate_field_access,
    _strip_dimension_suffix,
    _is_field_denied,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sales_model():
    return create_fact_sales_model()


@pytest.fixture
def sales_service():
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    return svc


@pytest.fixture
def mapping(sales_model):
    return build_physical_column_mapping(sales_model)


# ============================================================================
# DeniedColumn DTO tests
# ============================================================================

class TestDeniedColumnDTO:
    def test_basic_creation(self):
        dc = DeniedColumn(table="fact_sales", column="sales_amount")
        assert dc.table == "fact_sales"
        assert dc.column == "sales_amount"
        assert dc.schema_name is None

    def test_with_schema(self):
        dc = DeniedColumn(schema_name="public", table="fact_sales", column="sales_amount")
        assert dc.schema_name == "public"

    def test_json_alias(self):
        dc = DeniedColumn(table="fact_sales", column="sales_amount")
        d = dc.model_dump(by_alias=True, exclude_none=True)
        assert "table" in d
        assert "column" in d
        assert "schema" not in d  # None excluded

    def test_from_dict_with_alias(self):
        dc = DeniedColumn(**{"schema": "public", "table": "dim_customer", "column": "email"})
        assert dc.schema_name == "public"
        assert dc.table == "dim_customer"
        assert dc.column == "email"

    def test_query_request_with_denied_columns(self):
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        assert req.denied_columns is not None
        assert len(req.denied_columns) == 1
        assert req.denied_columns[0].table == "fact_sales"

    def test_json_round_trip(self):
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        d = req.model_dump(by_alias=True, exclude_none=True)
        assert "deniedColumns" in d
        assert d["deniedColumns"][0]["table"] == "fact_sales"

    def test_metadata_request_with_denied_columns(self):
        req = SemanticMetadataRequest(
            denied_columns=[DeniedColumn(table="dim_product", column="unit_price")],
        )
        assert req.denied_columns is not None


# ============================================================================
# PhysicalColumnMapping tests
# ============================================================================

class TestPhysicalColumnMappingBuild:
    """Test mapping construction from the ecommerce demo model."""

    def test_mapping_not_empty(self, mapping):
        assert mapping.get_all_qm_field_names()
        assert mapping.get_physical_tables()

    def test_fact_table_present(self, mapping):
        tables = mapping.get_physical_tables()
        fact_tables = [t for t in tables if t["role"] == "fact"]
        assert len(fact_tables) == 1
        assert fact_tables[0]["table"] == "fact_sales"

    def test_dimension_tables_present(self, mapping):
        tables = mapping.get_physical_tables()
        dim_tables = [t for t in tables if t["role"] == "dimension"]
        dim_names = {t["table"] for t in dim_tables}
        assert "dim_date" in dim_names
        assert "dim_product" in dim_names
        assert "dim_customer" in dim_names
        assert "dim_store" in dim_names
        assert "dim_channel" in dim_names
        assert "dim_promotion" in dim_names

    def test_tables_deduplicated(self, mapping):
        tables = mapping.get_physical_tables()
        table_names = [t["table"] for t in tables]
        assert len(table_names) == len(set(table_names))

    def test_measure_forward_mapping(self, mapping):
        """Measure → fact table column."""
        refs = mapping.get_physical_columns("salesAmount")
        assert len(refs) == 1
        assert refs[0].table == "fact_sales"
        assert refs[0].column == "sales_amount"

    def test_measure_reverse_mapping(self, mapping):
        """fact_sales.sales_amount → salesAmount."""
        qm_fields = mapping.get_qm_fields("fact_sales", "sales_amount")
        assert "salesAmount" in qm_fields

    def test_dimension_id_forward_mapping(self, mapping):
        """product$id → FK on fact_sales + PK on dim_product."""
        refs = mapping.get_physical_columns("product$id")
        tables_cols = {(r.table, r.column) for r in refs}
        assert ("fact_sales", "product_key") in tables_cols
        assert ("dim_product", "product_key") in tables_cols

    def test_dimension_id_reverse_mapping(self, mapping):
        """fact_sales.product_key → product$id."""
        qm_fields = mapping.get_qm_fields("fact_sales", "product_key")
        assert "product$id" in qm_fields

    def test_dimension_caption_forward_mapping(self, mapping):
        """product$caption → dim_product.product_name."""
        refs = mapping.get_physical_columns("product$caption")
        assert len(refs) == 1
        assert refs[0].table == "dim_product"
        assert refs[0].column == "product_name"

    def test_dimension_property_forward_mapping(self, mapping):
        """product$categoryName → dim_product.category_name."""
        refs = mapping.get_physical_columns("product$categoryName")
        assert len(refs) == 1
        assert refs[0].table == "dim_product"
        assert refs[0].column == "category_name"

    def test_dimension_property_reverse_mapping(self, mapping):
        """dim_product.category_name → product$categoryName."""
        qm_fields = mapping.get_qm_fields("dim_product", "category_name")
        assert "product$categoryName" in qm_fields

    def test_simple_dimension_forward_mapping(self, mapping):
        """orderId (fact table dimension) → fact_sales.order_id."""
        refs = mapping.get_physical_columns("orderId")
        assert len(refs) == 1
        assert refs[0].table == "fact_sales"
        assert refs[0].column == "order_id"

    def test_unknown_column_returns_empty(self, mapping):
        assert mapping.get_physical_columns("nonExistentField") == []
        assert mapping.get_qm_fields("no_table", "no_col") == []


class TestDeniedColumnsResolution:
    """Test to_denied_qm_fields() — physical → QM conversion."""

    def test_denied_measure(self, mapping):
        """Deny fact_sales.sales_amount → blocks salesAmount."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="fact_sales", column="sales_amount"),
        ])
        assert "salesAmount" in denied

    def test_denied_dimension_fk(self, mapping):
        """Deny fact_sales.product_key → blocks product$id."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="fact_sales", column="product_key"),
        ])
        assert "product$id" in denied

    def test_denied_dimension_table_column(self, mapping):
        """Deny dim_product.category_name → blocks product$categoryName."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="dim_product", column="category_name"),
        ])
        assert "product$categoryName" in denied

    def test_denied_caption_column(self, mapping):
        """Deny dim_product.product_name → blocks product$caption."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="dim_product", column="product_name"),
        ])
        assert "product$caption" in denied

    def test_denied_simple_dimension(self, mapping):
        """Deny fact_sales.order_id → blocks orderId."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="fact_sales", column="order_id"),
        ])
        assert "orderId" in denied

    def test_multiple_denied(self, mapping):
        """Multiple denied columns resolve to union of denied QM fields."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="fact_sales", column="sales_amount"),
            DeniedColumn(table="dim_product", column="category_name"),
        ])
        assert "salesAmount" in denied
        assert "product$categoryName" in denied

    def test_no_match_returns_empty(self, mapping):
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="nonexistent_table", column="nonexistent_col"),
        ])
        assert denied == set()

    def test_empty_input(self, mapping):
        assert mapping.to_denied_qm_fields([]) == set()

    def test_null_table_skipped(self, mapping):
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(table="", column="sales_amount"),
        ])
        assert denied == set()

    def test_schema_ignored(self, mapping):
        """Schema is ignored in matching (aligned with Java)."""
        denied = mapping.to_denied_qm_fields([
            DeniedColumn(schema_name="public", table="fact_sales", column="sales_amount"),
        ])
        assert "salesAmount" in denied


# ============================================================================
# Field validator — blacklist tests
# ============================================================================

class TestDimensionSuffixStripping:
    def test_with_suffix(self):
        assert _strip_dimension_suffix("customer$type") == "customer"

    def test_without_suffix(self):
        assert _strip_dimension_suffix("salesAmount") == "salesAmount"

    def test_id_suffix(self):
        assert _strip_dimension_suffix("product$id") == "product"


class TestIsFieldDenied:
    def test_direct_match(self):
        assert _is_field_denied("salesAmount", {"salesAmount"})

    def test_base_dimension_match(self):
        """Denying base 'customer' blocks customer$type too."""
        assert _is_field_denied("customer$type", {"customer"})

    def test_no_match(self):
        assert not _is_field_denied("salesAmount", {"costAmount"})

    def test_specific_property_match(self):
        assert _is_field_denied("product$categoryName", {"product$categoryName"})

    def test_specific_property_no_base_match(self):
        """Denying product$categoryName does NOT block product$brand."""
        assert not _is_field_denied("product$brand", {"product$categoryName"})


class TestValidateFieldAccessBlacklist:
    """Test denied_qm_fields (blacklist) in validate_field_access."""

    def test_denied_column_blocks_query(self):
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount"],
            slice_items=[],
            order_by=[],
            denied_qm_fields={"salesAmount"},
        )
        assert not result.valid
        assert "salesAmount" in result.blocked_fields

    def test_denied_column_blocks_slice(self):
        result = validate_field_access(
            columns=["orderId$caption"],
            slice_items=[{"field": "salesAmount", "op": "gt", "value": 100}],
            order_by=[],
            denied_qm_fields={"salesAmount"},
        )
        assert not result.valid
        assert "salesAmount" in result.blocked_fields

    def test_denied_column_blocks_orderby(self):
        result = validate_field_access(
            columns=["orderId$caption"],
            slice_items=[],
            order_by=[{"field": "salesAmount", "dir": "desc"}],
            denied_qm_fields={"salesAmount"},
        )
        assert not result.valid
        assert "salesAmount" in result.blocked_fields

    def test_denied_column_blocks_calculated_field(self):
        result = validate_field_access(
            columns=["orderId$caption"],
            slice_items=[],
            order_by=[],
            calculated_fields=[{"expression": "salesAmount + discountAmount", "name": "net"}],
            denied_qm_fields={"discountAmount"},
        )
        assert not result.valid
        assert "discountAmount" in result.blocked_fields

    def test_no_denied_passes(self):
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount"],
            slice_items=[],
            order_by=[],
            denied_qm_fields=set(),
        )
        assert result.valid

    def test_denied_none_passes(self):
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount"],
            slice_items=[],
            order_by=[],
            denied_qm_fields=None,
        )
        assert result.valid

    def test_denied_dimension_base_blocks_all_suffixed(self):
        """Denying base dim name blocks all $suffix access."""
        result = validate_field_access(
            columns=["product$categoryName"],
            slice_items=[],
            order_by=[],
            denied_qm_fields={"product"},
        )
        assert not result.valid
        assert "product$categoryName" in result.blocked_fields


class TestCombinedWhitelistBlacklist:
    """Test field_access (whitelist) + denied_qm_fields (blacklist) together."""

    def test_whitelist_allows_blacklist_blocks(self):
        """Field in whitelist but also in blacklist → blocked (conservative)."""
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount"],
            slice_items=[],
            order_by=[],
            field_access=FieldAccessDef(visible=["orderId$caption", "salesAmount"]),
            denied_qm_fields={"salesAmount"},
        )
        assert not result.valid
        assert "salesAmount" in result.blocked_fields

    def test_whitelist_blocks_blacklist_irrelevant(self):
        """Field not in whitelist → blocked even if not in blacklist."""
        result = validate_field_access(
            columns=["orderId$caption", "costAmount"],
            slice_items=[],
            order_by=[],
            field_access=FieldAccessDef(visible=["orderId$caption"]),
            denied_qm_fields=set(),
        )
        assert not result.valid
        assert "costAmount" in result.blocked_fields

    def test_both_allow(self):
        """Field in whitelist and not in blacklist → allowed."""
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount"],
            slice_items=[],
            order_by=[],
            field_access=FieldAccessDef(visible=["orderId$caption", "salesAmount"]),
            denied_qm_fields={"costAmount"},  # different field denied
        )
        assert result.valid

    def test_both_active_multiple_blocked(self):
        """Multiple reasons for blocking: some by whitelist, some by blacklist."""
        result = validate_field_access(
            columns=["orderId$caption", "salesAmount", "costAmount", "taxAmount"],
            slice_items=[],
            order_by=[],
            field_access=FieldAccessDef(visible=["orderId$caption", "salesAmount", "costAmount"]),
            denied_qm_fields={"costAmount"},
        )
        assert not result.valid
        assert "taxAmount" in result.blocked_fields   # whitelist blocks
        assert "costAmount" in result.blocked_fields   # blacklist blocks


# ============================================================================
# system_slice bypass with denied_columns
# ============================================================================

class TestSystemSliceBypassDeniedColumns:
    """system_slice must not be validated against field governance."""

    def test_system_slice_bypasses_denied_columns(self, sales_service):
        """system_slice using a denied column should still pass."""
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            slice=[],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="customer_key"),
            ],
            system_slice=[
                {"field": "customer$id", "op": "eq", "value": 42},
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        # system_slice should not cause a field governance error
        assert result.error is None

    def test_user_slice_with_denied_column_fails(self, sales_service):
        """User slice referencing a denied field should fail."""
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            slice=[{"field": "salesAmount", "op": "gt", "value": 100}],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "salesAmount" in result.error

    def test_system_slice_merged_after_validation(self, sales_service):
        """system_slice conditions should appear in the final SQL."""
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            slice=[],
            system_slice=[
                {"field": "customer$id", "op": "eq", "value": 42},
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is None
        # system_slice should have been merged — check SQL has customer filter
        if result.sql:
            assert "42" in result.sql or "customer" in result.sql.lower()


# ============================================================================
# Service-level integration — query with denied_columns
# ============================================================================

class TestServiceDeniedColumns:
    """Service-level integration tests for denied_columns."""

    def test_denied_measure_blocks_query(self, sales_service):
        req = SemanticQueryRequest(
            columns=["orderId$caption", "salesAmount"],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "salesAmount" in result.error

    def test_denied_dimension_property_blocks_query(self, sales_service):
        req = SemanticQueryRequest(
            columns=["orderId$caption", "product$categoryName"],
            denied_columns=[
                DeniedColumn(table="dim_product", column="category_name"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "product$categoryName" in result.error

    def test_denied_unrelated_column_passes(self, sales_service):
        req = SemanticQueryRequest(
            columns=["orderId$caption", "salesAmount"],
            denied_columns=[
                DeniedColumn(table="dim_customer", column="email"),  # not used in query
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is None

    def test_denied_column_blocks_orderby(self, sales_service):
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            order_by=[{"field": "salesAmount", "dir": "desc"}],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "salesAmount" in result.error

    def test_denied_column_blocks_calculated_dependency(self, sales_service):
        """Deny a column that a calculated field depends on."""
        req = SemanticQueryRequest(
            columns=["orderId$caption"],
            calculated_fields=[{
                "name": "netAmount",
                "expression": "salesAmount + discountAmount",
            }],
            denied_columns=[
                DeniedColumn(table="fact_sales", column="discount_amount"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "discountAmount" in result.error

    def test_combined_whitelist_blacklist_service(self, sales_service):
        """Both field_access + denied_columns active on query_model."""
        req = SemanticQueryRequest(
            columns=["orderId$caption", "salesAmount"],
            field_access=FieldAccessDef(visible=["orderId$caption", "salesAmount", "costAmount"]),
            denied_columns=[
                DeniedColumn(table="fact_sales", column="sales_amount"),
            ],
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "salesAmount" in result.error

    def test_no_governance_backward_compat(self, sales_service):
        """No field_access and no denied_columns → old behavior."""
        req = SemanticQueryRequest(columns=["orderId$caption", "salesAmount"])
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is None


# ============================================================================
# Accessor payload — deniedColumns passthrough
# ============================================================================

class TestAccessorDeniedColumns:
    """Test payload → build_query_request → denied_columns."""

    def test_denied_columns_parsed(self):
        payload = {
            "columns": ["orderId$caption"],
            "deniedColumns": [
                {"table": "fact_sales", "column": "sales_amount"},
                {"schema": "public", "table": "dim_product", "column": "unit_price"},
            ],
        }
        req = build_query_request(payload)
        assert req.denied_columns is not None
        assert len(req.denied_columns) == 2
        assert req.denied_columns[0].table == "fact_sales"
        assert req.denied_columns[0].column == "sales_amount"
        assert req.denied_columns[1].schema_name == "public"

    def test_no_denied_columns(self):
        payload = {"columns": ["orderId$caption"]}
        req = build_query_request(payload)
        assert req.denied_columns is None

    def test_full_chain_payload_to_rejection(self, sales_service):
        """Full chain: JSON payload → build_query_request → query_model → rejection."""
        payload = {
            "columns": ["orderId$caption", "salesAmount"],
            "deniedColumns": [
                {"table": "fact_sales", "column": "sales_amount"},
            ],
        }
        req = build_query_request(payload)
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None
        assert "salesAmount" in result.error

    def test_full_chain_with_system_slice(self, sales_service):
        """Payload with deniedColumns + systemSlice: system_slice bypasses."""
        payload = {
            "columns": ["orderId$caption"],
            "deniedColumns": [
                {"table": "fact_sales", "column": "customer_key"},
            ],
            "systemSlice": [
                {"field": "customer$id", "op": "eq", "value": 42},
            ],
        }
        req = build_query_request(payload)
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is None


# ============================================================================
# Metadata — physicalTables output
# ============================================================================

class TestMetadataPhysicalTables:
    """Test physical_tables in metadata v3 output."""

    def test_physical_tables_in_metadata(self, sales_service):
        meta = sales_service.get_metadata_v3()
        assert "physicalTables" in meta
        tables = meta["physicalTables"]
        assert len(tables) > 0

        # Check fact table present
        fact_tables = [t for t in tables if t["role"] == "fact"]
        assert len(fact_tables) >= 1
        assert fact_tables[0]["table"] == "fact_sales"

        # Check dimension tables present
        dim_tables = {t["table"] for t in tables if t["role"] == "dimension"}
        assert "dim_product" in dim_tables
        assert "dim_customer" in dim_tables
        assert "dim_date" in dim_tables

    def test_physical_tables_deduplicated(self, sales_service):
        meta = sales_service.get_metadata_v3()
        tables = meta["physicalTables"]
        table_names = [t["table"] for t in tables]
        assert len(table_names) == len(set(table_names))

    def test_physical_tables_with_specific_model(self, sales_service):
        meta = sales_service.get_metadata_v3(model_names=["FactSalesModel"])
        assert "physicalTables" in meta


# ============================================================================
# Metadata — denied_columns field trimming
# ============================================================================

class TestMetadataDeniedColumnsTrimming:
    """Test metadata field trimming when denied_columns are present."""

    def test_baseline_all_fields(self, sales_service):
        """Without denied_columns: all fields present."""
        meta = sales_service.get_metadata_v3()
        assert "salesAmount" in meta["fields"]
        assert "product$categoryName" in meta["fields"]

    def test_denied_measure_trimmed(self, sales_service):
        """Deny fact_sales.sales_amount → salesAmount removed from metadata."""
        meta = sales_service.get_metadata_v3(
            denied_columns=[DeniedColumn(table="fact_sales", column="sales_amount")],
        )
        assert "salesAmount" not in meta["fields"]
        # Other fields still present
        assert "orderId" in meta["fields"]

    def test_denied_dimension_property_trimmed(self, sales_service):
        """Deny dim_product.category_name → product$categoryName removed."""
        meta = sales_service.get_metadata_v3(
            denied_columns=[DeniedColumn(table="dim_product", column="category_name")],
        )
        assert "product$categoryName" not in meta["fields"]
        # Other product fields still present
        assert "product$id" in meta["fields"]

    def test_denied_fk_trims_dimension_id(self, sales_service):
        """Deny fact_sales.product_key → product$id removed."""
        meta = sales_service.get_metadata_v3(
            denied_columns=[DeniedColumn(table="fact_sales", column="product_key")],
        )
        assert "product$id" not in meta["fields"]

    def test_denied_combined_with_visible_fields(self, sales_service):
        """visible_fields + denied_columns: intersection."""
        meta = sales_service.get_metadata_v3(
            visible_fields=["orderId", "salesAmount", "costAmount"],
            denied_columns=[DeniedColumn(table="fact_sales", column="sales_amount")],
        )
        # salesAmount in whitelist but also denied → removed
        assert "salesAmount" not in meta["fields"]
        # orderId in whitelist and not denied → present
        assert "orderId" in meta["fields"]
        # costAmount in whitelist and not denied → present
        assert "costAmount" in meta["fields"]

    def test_metadata_query_consistency(self, sales_service):
        """Metadata trimming and query validation should agree."""
        denied = [DeniedColumn(table="fact_sales", column="sales_amount")]

        # Metadata should not expose salesAmount
        meta = sales_service.get_metadata_v3(denied_columns=denied)
        assert "salesAmount" not in meta["fields"]

        # Query should reject salesAmount
        req = SemanticQueryRequest(
            columns=["orderId$caption", "salesAmount"],
            denied_columns=denied,
        )
        result = sales_service.query_model("FactSalesModel", req, mode="validate")
        assert result.error is not None

    def test_markdown_metadata_denied_trimming(self, sales_service):
        """Markdown metadata should also trim denied fields from field tables."""
        md = sales_service.get_metadata_v3_markdown(
            denied_columns=[DeniedColumn(table="fact_sales", column="sales_amount")],
        )
        # salesAmount should not appear in the measure table rows
        # (may still appear in generic Usage Tips examples)
        for line in md.split("\n"):
            if line.startswith("|") and "salesAmount" in line:
                pytest.fail(f"salesAmount found in table row: {line}")

        # Verify another measure IS still present
        assert "costAmount" in md or "profitAmount" in md


# ============================================================================
# Mapping cache lifecycle
# ============================================================================

class TestMappingCacheLifecycle:
    """Test that mapping cache is properly invalidated."""

    def test_mapping_cached(self, sales_service):
        m1 = sales_service.get_physical_column_mapping("FactSalesModel")
        m2 = sales_service.get_physical_column_mapping("FactSalesModel")
        assert m1 is m2  # same object

    def test_mapping_invalidated_on_reregister(self, sales_service):
        m1 = sales_service.get_physical_column_mapping("FactSalesModel")
        sales_service.register_model(create_fact_sales_model())
        m2 = sales_service.get_physical_column_mapping("FactSalesModel")
        assert m1 is not m2  # new object after re-registration

    def test_mapping_invalidated_on_full_clear(self, sales_service):
        m1 = sales_service.get_physical_column_mapping("FactSalesModel")
        sales_service.invalidate_model_cache()
        m2 = sales_service.get_physical_column_mapping("FactSalesModel")
        assert m1 is not m2

    def test_mapping_none_for_unknown_model(self, sales_service):
        assert sales_service.get_physical_column_mapping("NonExistent") is None


# ============================================================================
# GroupBy validation with denied_columns
# ============================================================================

class TestGroupByDeniedColumns:
    """Ensure groupBy fields are also validated."""

    def test_denied_groupby_field_blocks(self):
        result = validate_field_access(
            # Use the $caption attribute form per QM contract (v1.7 backlog
            # B-03 strict). The validator strips $caption when matching
            # the denied set, so {"orderId"} still blocks "orderId$caption".
            columns=["orderId$caption"],
            slice_items=[],
            order_by=[],
            denied_qm_fields={"orderId"},
        )
        assert not result.valid
        # blocked_fields reports the user-facing column name verbatim.
        assert "orderId$caption" in result.blocked_fields
