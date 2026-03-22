"""
Unit tests for FSScript TM file loading:
- _snake_to_camel()
- _adapt_fsscript_tm()
- load_models_from_directory()
"""

import pytest
import tempfile
from pathlib import Path

from foggy.dataset_model.impl.loader import (
    _snake_to_camel,
    _adapt_fsscript_tm,
    load_models_from_directory,
)


# ==================== _snake_to_camel ====================


class TestSnakeToCamel:
    """Tests for snake_case → camelCase conversion (Java alignment)."""

    def test_simple_two_parts(self):
        assert _snake_to_camel("user_id") == "userId"

    def test_three_parts(self):
        assert _snake_to_camel("date_order_time") == "dateOrderTime"

    def test_single_word(self):
        assert _snake_to_camel("id") == "id"

    def test_already_camel(self):
        assert _snake_to_camel("orderId") == "orderId"

    def test_underscore_prefix(self):
        # Leading empty part: "" + "id" → "Id" — edge case
        result = _snake_to_camel("_id")
        assert result == "Id"

    def test_all_lowercase(self):
        assert _snake_to_camel("amount_untaxed") == "amountUntaxed"

    def test_sub_category_name(self):
        assert _snake_to_camel("sub_category_name") == "subCategoryName"

    def test_is_weekend(self):
        assert _snake_to_camel("is_weekend") == "isWeekend"

    def test_empty_string(self):
        assert _snake_to_camel("") == ""

    def test_no_underscore(self):
        assert _snake_to_camel("name") == "name"

    def test_multiple_underscores(self):
        assert _snake_to_camel("a_b_c_d") == "aBCD"


# ==================== _adapt_fsscript_tm ====================


class TestAdaptFsscriptTm:
    """Tests for FSScript → JdbcTableModelLoader dict adaptation."""

    def test_idcolumn_to_primarykey(self):
        result = _adapt_fsscript_tm({"idColumn": "id"})
        assert result.get("primaryKey") == "id"
        assert "idColumn" not in result

    def test_primarykey_not_overwritten(self):
        """If both idColumn and primaryKey exist, primaryKey wins."""
        result = _adapt_fsscript_tm({"idColumn": "id", "primaryKey": "pk"})
        assert result.get("primaryKey") == "pk"

    def test_caption_to_alias_model_level(self):
        result = _adapt_fsscript_tm({"caption": "Sales"})
        assert result["alias"] == "Sales"

    def test_existing_alias_not_overwritten(self):
        result = _adapt_fsscript_tm({"caption": "Sales", "alias": "MySales"})
        assert result["alias"] == "MySales"

    def test_dimension_foreignkey_to_column(self):
        result = _adapt_fsscript_tm({
            "dimensions": [{"name": "partner", "foreignKey": "partner_id"}],
        })
        dim = result["dimensions"][0]
        assert dim["column"] == "partner_id"

    def test_dimension_caption_to_alias(self):
        result = _adapt_fsscript_tm({
            "dimensions": [{"name": "d", "caption": "Customer"}],
        })
        assert result["dimensions"][0]["alias"] == "Customer"

    def test_dimension_property_name_from_column_camelcase(self):
        result = _adapt_fsscript_tm({
            "dimensions": [{
                "name": "d",
                "properties": [
                    {"column": "customer_rank"},
                    {"column": "city"},
                    {"column": "is_company", "name": "isCompany"},  # explicit
                ],
            }],
        })
        props = result["dimensions"][0]["properties"]
        assert props[0]["name"] == "customerRank"
        assert props[1]["name"] == "city"
        assert props[2]["name"] == "isCompany"  # not overwritten

    def test_measure_name_from_column_camelcase(self):
        result = _adapt_fsscript_tm({
            "measures": [
                {"column": "amount_untaxed", "caption": "Untaxed"},
                {"column": "id", "name": "orderCount"},  # explicit
            ],
        })
        assert result["measures"][0]["name"] == "amountUntaxed"
        assert result["measures"][0]["alias"] == "Untaxed"
        assert result["measures"][1]["name"] == "orderCount"

    def test_property_name_from_column_camelcase(self):
        result = _adapt_fsscript_tm({
            "properties": [
                {"column": "date_order", "caption": "Order Date"},
                {"column": "id"},
                {"column": "client_order_ref", "name": "clientRef"},
            ],
        })
        assert result["properties"][0]["name"] == "dateOrder"
        assert result["properties"][1]["name"] == "id"
        assert result["properties"][2]["name"] == "clientRef"

    def test_full_odoo_like_model(self):
        """Test adaptation of a realistic Odoo-style FSScript export."""
        model_def = {
            "name": "OdooSaleOrderModel",
            "caption": "Sale Orders",
            "tableName": "sale_order",
            "idColumn": "id",
            "dimensions": [
                {
                    "name": "partner",
                    "tableName": "res_partner",
                    "foreignKey": "partner_id",
                    "primaryKey": "id",
                    "captionColumn": "name",
                    "caption": "Customer",
                    "properties": [
                        {"column": "customer_rank", "caption": "Customer Rank", "type": "INTEGER"},
                    ],
                },
            ],
            "properties": [
                {"column": "date_order", "caption": "Order Date", "type": "DATETIME"},
            ],
            "measures": [
                {"column": "amount_total", "caption": "Total", "type": "MONEY", "aggregation": "sum"},
                {"column": "id", "name": "orderCount", "caption": "Order Count", "aggregation": "COUNT_DISTINCT"},
            ],
        }

        result = _adapt_fsscript_tm(model_def)

        assert result["primaryKey"] == "id"
        assert result["alias"] == "Sale Orders"
        assert result["dimensions"][0]["column"] == "partner_id"
        assert result["dimensions"][0]["alias"] == "Customer"
        assert result["dimensions"][0]["properties"][0]["name"] == "customerRank"
        assert result["properties"][0]["name"] == "dateOrder"
        assert result["measures"][0]["name"] == "amountTotal"
        assert result["measures"][1]["name"] == "orderCount"

    def test_empty_lists(self):
        result = _adapt_fsscript_tm({
            "dimensions": [],
            "measures": [],
            "properties": [],
        })
        assert result["dimensions"] == []
        assert result["measures"] == []
        assert result["properties"] == []

    def test_no_lists(self):
        result = _adapt_fsscript_tm({"name": "empty"})
        assert result["dimensions"] == []
        assert result["measures"] == []
        assert result["properties"] == []

    def test_non_dict_items_skipped(self):
        result = _adapt_fsscript_tm({
            "dimensions": [None, "invalid", {"name": "ok"}],
            "measures": [None, {"column": "x"}],
            "properties": [42],
        })
        assert len(result["dimensions"]) == 1
        assert len(result["measures"]) == 1
        assert len(result["properties"]) == 0


# ==================== load_models_from_directory ====================


class TestLoadModelsFromDirectory:
    """Tests for loading FSScript .tm files from a directory."""

    @pytest.fixture
    def tm_dir(self):
        """Create a temp directory with FSScript .tm files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simple TM without imports
            (Path(tmpdir) / "SimpleModel.tm").write_text(
                """
export const model = {
    name: 'SimpleModel',
    caption: 'Simple',
    tableName: 'simple_table',
    idColumn: 'id',
    dimensions: [
        {
            name: 'category',
            tableName: 'dim_category',
            foreignKey: 'category_id',
            primaryKey: 'id',
            captionColumn: 'name',
            caption: 'Category'
        }
    ],
    properties: [
        { column: 'order_date', caption: 'Order Date', type: 'DATETIME' }
    ],
    measures: [
        { column: 'amount', caption: 'Amount', aggregation: 'sum' },
        { column: 'id', name: 'count', caption: 'Count', aggregation: 'COUNT_DISTINCT' }
    ]
};
""",
                encoding="utf-8",
            )

            # Second TM
            (Path(tmpdir) / "AnotherModel.tm").write_text(
                """
export const model = {
    name: 'AnotherModel',
    caption: 'Another',
    tableName: 'another_table',
    idColumn: 'pk',
    dimensions: [],
    measures: []
};
""",
                encoding="utf-8",
            )

            yield tmpdir

    @pytest.fixture
    def tm_dir_with_subdirs(self):
        """Create a temp directory with nested .tm files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "model"
            model_dir.mkdir()
            (model_dir / "SubModel.tm").write_text(
                """
export const model = {
    name: 'SubModel',
    caption: 'Sub',
    tableName: 'sub_table',
    idColumn: 'id'
};
""",
                encoding="utf-8",
            )
            yield tmpdir

    def test_load_basic_tm_files(self, tm_dir):
        models = load_models_from_directory(tm_dir)

        assert len(models) == 2
        names = {m.name for m in models}
        assert "SimpleModel" in names
        assert "AnotherModel" in names

    def test_model_fields(self, tm_dir):
        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        assert simple.alias == "Simple"
        assert simple.source_table == "simple_table"
        assert "id" in simple.primary_key
        assert "category" in simple.dimensions
        assert simple.dimensions["category"].alias == "Category"

    def test_snake_to_camel_applied(self, tm_dir):
        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        # property: order_date → orderDate
        assert "orderDate" in simple.columns

        # measure without name: amount → amount (no underscore, unchanged)
        assert "amount" in simple.measures
        # measure with explicit name
        assert "count" in simple.measures

    def test_recursive_scan(self, tm_dir_with_subdirs):
        models = load_models_from_directory(tm_dir_with_subdirs)
        assert len(models) == 1
        assert models[0].name == "SubModel"

    def test_nonexistent_directory(self):
        models = load_models_from_directory("/nonexistent/path/12345")
        assert models == []

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            models = load_models_from_directory(tmpdir)
            assert models == []

    def test_invalid_tm_file_skipped(self):
        """A malformed .tm file should not crash loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid
            (Path(tmpdir) / "Good.tm").write_text(
                "export const model = { name: 'Good', tableName: 't' };",
                encoding="utf-8",
            )
            # Invalid syntax
            (Path(tmpdir) / "Bad.tm").write_text(
                "this is not valid fsscript @@@@",
                encoding="utf-8",
            )

            models = load_models_from_directory(tmpdir)
            # Should still load the good one
            assert len(models) >= 1
            assert any(m.name == "Good" for m in models)

    def test_tm_without_model_export_skipped(self):
        """A .tm file without export const model should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "NoExport.tm").write_text(
                "const x = 42;",
                encoding="utf-8",
            )
            models = load_models_from_directory(tmpdir)
            assert models == []

    def test_datasource_name_preserved(self):
        """dataSourceName field should flow through to source_datasource."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "OdooModel.tm").write_text(
                """
export const model = {
    name: 'OdooModel',
    tableName: 'sale_order',
    dataSourceName: 'odoo',
    idColumn: 'id'
};
""",
                encoding="utf-8",
            )
            models = load_models_from_directory(tmpdir)
            assert len(models) == 1
            assert models[0].source_datasource == "odoo"
