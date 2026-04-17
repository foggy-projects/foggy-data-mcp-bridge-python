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
    _TmRefProxy,
    _extract_allowed_fields,
    _apply_column_group_filter,
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

    def test_dimension_joins_created(self, tm_dir):
        """Dimensions with tableName should create DimensionJoinDef entries."""
        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        assert len(simple.dimension_joins) == 1
        j = simple.dimension_joins[0]
        assert j.name == "category"
        assert j.table_name == "dim_category"
        assert j.foreign_key == "category_id"
        assert j.primary_key == "id"
        assert j.caption_column == "name"
        assert j.caption == "Category"

    def test_dimension_join_caption_query(self, tm_dir):
        """dim$caption should resolve via DimensionJoinDef and generate JOIN."""
        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        resolved = simple.resolve_field("category$caption")
        assert resolved is not None
        assert "dim_category" in resolved["sql_expr"] or "dc" in resolved["sql_expr"]
        assert resolved["join_def"] is not None

    def test_property_resolve_field(self, tm_dir):
        """Properties should be resolvable via resolve_field()."""
        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        resolved = simple.resolve_field("orderDate")
        assert resolved is not None
        assert "order_date" in resolved["sql_expr"]  # SQL uses original column name
        assert resolved["is_measure"] is False

    def test_property_sql_uses_original_column(self, tm_dir):
        """Property SQL should use the original snake_case column, not camelCase name."""
        from foggy.dataset_model.semantic.service import SemanticQueryService
        from foggy.mcp_spi import SemanticQueryRequest

        models = load_models_from_directory(tm_dir)
        simple = next(m for m in models if m.name == "SimpleModel")

        svc = SemanticQueryService()
        svc.register_model(simple)
        r = svc.query_model("SimpleModel", SemanticQueryRequest(columns=["orderDate"], limit=5), mode="validate")

        assert r.error is None
        assert not r.warnings
        assert "order_date" in r.sql  # original column name in SQL

    def test_at_service_import_handled(self):
        """@service imports should not crash loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # dicts.fsscript with @service import
            (Path(tmpdir) / "dicts.fsscript").write_text(
                """
import { registerDict } from '@jdbcModelDictService';
export const dicts = {
    status: registerDict({ id: 'status', items: [{value: 'a', label: 'A'}] })
};
""",
                encoding="utf-8",
            )
            # TM that imports dicts
            model_dir = Path(tmpdir) / "model"
            model_dir.mkdir()
            (model_dir / "TestModel.tm").write_text(
                """
import { dicts } from '../dicts.fsscript';
export const model = {
    name: 'TestModel',
    tableName: 'test',
    idColumn: 'id',
    properties: [
        { column: 'status', caption: 'Status', dictRef: dicts.status }
    ]
};
""",
                encoding="utf-8",
            )
            models = load_models_from_directory(tmpdir)
            assert len(models) == 1
            assert models[0].name == "TestModel"

    def test_qm_files_loaded(self):
        """QM files should be loaded as aliases to their referenced TM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "model"
            model_dir.mkdir()
            (model_dir / "SalesModel.tm").write_text(
                """
export const model = {
    name: 'SalesModel',
    caption: 'Sales',
    tableName: 'sales',
    idColumn: 'id',
    measures: [
        { column: 'amount', name: 'amount', caption: 'Amount', aggregation: 'sum' }
    ]
};
""",
                encoding="utf-8",
            )
            query_dir = Path(tmpdir) / "query"
            query_dir.mkdir()
            (query_dir / "SalesQueryModel.qm").write_text(
                """
const s = loadTableModel('SalesModel');
export const queryModel = {
    name: 'SalesQueryModel',
    caption: 'Sales Query',
    description: 'Query sales data',
    model: s
};
""",
                encoding="utf-8",
            )

            models = load_models_from_directory(tmpdir)
            names = {m.name for m in models}
            assert "SalesModel" in names
            assert "SalesQueryModel" in names

            qm = next(m for m in models if m.name == "SalesQueryModel")
            assert qm.alias == "Sales Query"
            assert qm.source_table == "sales"  # inherited from TM
            assert "amount" in qm.measures  # inherited from TM

    def test_qm_unknown_tm_skipped(self):
        """QM referencing unknown TM should be skipped (not crash)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            query_dir = Path(tmpdir) / "query"
            query_dir.mkdir()
            # Need at least one .tm to not short-circuit
            (Path(tmpdir) / "Dummy.tm").write_text(
                "export const model = { name: 'Dummy', tableName: 't' };",
                encoding="utf-8",
            )
            (query_dir / "OrphanQM.qm").write_text(
                """
const x = loadTableModel('NonExistent');
export const queryModel = { name: 'OrphanQM', model: x };
""",
                encoding="utf-8",
            )
            models = load_models_from_directory(tmpdir)
            names = {m.name for m in models}
            assert "Dummy" in names
            assert "OrphanQM" not in names

    def test_odoo_demo_models_full_load(self):
        """Integration test: load actual Odoo demo TM/QM files."""
        import os
        odoo_dir = os.path.join("src", "foggy", "demo", "models", "odoo")
        if not os.path.exists(odoo_dir):
            pytest.skip("Odoo demo models not found")

        models = load_models_from_directory(odoo_dir)
        names = {m.name for m in models}

        # 8 TMs
        assert "OdooSaleOrderModel" in names
        assert "OdooHrEmployeeModel" in names
        assert "OdooAccountMoveModel" in names

        # QMs
        assert "OdooSaleOrderQueryModel" in names
        assert "OdooHrEmployeeQueryModel" in names

        # Verify dimension JOINs exist
        sale = next(m for m in models if m.name == "OdooSaleOrderModel")
        assert len(sale.dimension_joins) >= 4  # partner, salesperson, company, salesTeam, ...
        assert any(j.name == "partner" for j in sale.dimension_joins)

        # Verify measures
        assert len(sale.measures) >= 4  # amountUntaxed, amountTax, amountTotal, ...
        assert "amountTotal" in sale.measures

        # Verify properties
        assert "dateOrder" in sale.columns


# ==================== columnGroups filtering ====================


class TestTmRefProxy:
    """Tests for _TmRefProxy — the loadTableModel() stub dict."""

    def test_get_always_returns_key_name(self):
        """proxy.get(key) should always return the key itself as a field ref."""
        proxy = _TmRefProxy({"__tm_ref__": "Sales", "name": "Sales"})
        # Even for keys present in the dict, get() returns the key name
        assert proxy.get("__tm_ref__") == "__tm_ref__"
        assert proxy.get("name") == "name"
        assert proxy.get("department") == "department"
        assert proxy.get("salesDate$year") == "salesDate$year"

    def test_internal_get_returns_real_value(self):
        """_internal_get() bypasses the proxy and returns stored values."""
        proxy = _TmRefProxy({"__tm_ref__": "Sales", "name": "Sales"})
        assert proxy._internal_get("__tm_ref__") == "Sales"
        assert proxy._internal_get("name") == "Sales"
        assert proxy._internal_get("department") is None

    def test_unknown_key_via_dict_bracket(self):
        """Standard dict[key] still raises KeyError for unknown keys."""
        proxy = _TmRefProxy({"__tm_ref__": "X"})
        with pytest.raises(KeyError):
            _ = proxy["missing"]


class TestExtractAllowedFields:
    """Tests for _extract_allowed_fields()."""

    def test_v2_ref_items(self):
        groups = [
            {
                "caption": "Org",
                "items": [
                    {"ref": "department"},
                    {"ref": "job"},
                ],
            }
        ]
        assert _extract_allowed_fields(groups) == {"department", "job"}

    def test_v1_name_items(self):
        groups = [
            {
                "caption": "Info",
                "items": [
                    {"name": "orderId"},
                    {"name": "status"},
                ],
            }
        ]
        assert _extract_allowed_fields(groups) == {"orderId", "status"}

    def test_formula_items_skipped(self):
        groups = [
            {
                "caption": "Advanced",
                "items": [
                    {"name": "profitRate", "formula": "profit / sales * 100", "type": "NUMBER"},
                ],
            }
        ]
        assert _extract_allowed_fields(groups) == set()

    def test_mixed_groups(self):
        groups = [
            {"caption": "G1", "items": [{"ref": "department"}]},
            {"caption": "G2", "items": [{"ref": "salesAmount"}, {"name": "calc", "formula": "1+1"}]},
        ]
        assert _extract_allowed_fields(groups) == {"department", "salesAmount"}

    def test_empty_groups(self):
        assert _extract_allowed_fields([]) == set()

    def test_dollar_refs(self):
        groups = [
            {
                "caption": "Date",
                "items": [
                    {"ref": "salesDate"},
                    {"ref": "salesDate$year"},
                    {"ref": "salesDate$month"},
                ],
            }
        ]
        assert _extract_allowed_fields(groups) == {"salesDate", "salesDate$year", "salesDate$month"}


class TestApplyColumnGroupFilter:
    """Tests for _apply_column_group_filter()."""

    def _make_model(self):
        """Create a test model with multiple dimensions, columns, measures."""
        from foggy.dataset_model.impl.model import (
            DbTableModelImpl,
            DbModelDimensionImpl,
            DbModelMeasureImpl,
            DimensionJoinDef,
        )
        from foggy.dataset_model.definitions.base import DbColumnDef

        return DbTableModelImpl(
            name="TestTM",
            source_table="test_table",
            dimensions={
                "department": DbModelDimensionImpl(name="department", column="department_id"),
                "job": DbModelDimensionImpl(name="job", column="job_id"),
                "user": DbModelDimensionImpl(name="user", column="user_id"),
            },
            dimension_joins=[
                DimensionJoinDef(name="department", table_name="hr_department", foreign_key="department_id", primary_key="id"),
                DimensionJoinDef(name="job", table_name="hr_job", foreign_key="job_id", primary_key="id"),
                DimensionJoinDef(name="user", table_name="res_users", foreign_key="user_id", primary_key="id"),
            ],
            columns={
                "id": DbColumnDef(name="id"),
                "name": DbColumnDef(name="name"),
                "email": DbColumnDef(name="email"),
            },
            measures={
                "employeeCount": DbModelMeasureImpl(name="employeeCount", column="id"),
                "salary": DbModelMeasureImpl(name="salary", column="salary"),
            },
        )

    def test_filter_removes_unreferenced_dimensions(self):
        model = self._make_model()
        allowed = {"department", "job", "id", "name", "employeeCount"}
        _apply_column_group_filter(model, allowed)

        assert "department" in model.dimensions
        assert "job" in model.dimensions
        assert "user" not in model.dimensions  # filtered out

    def test_filter_removes_unreferenced_dimension_joins(self):
        model = self._make_model()
        allowed = {"department", "id", "employeeCount"}
        _apply_column_group_filter(model, allowed)

        join_names = {j.name for j in model.dimension_joins}
        assert "department" in join_names
        assert "job" not in join_names
        assert "user" not in join_names

    def test_filter_removes_unreferenced_columns(self):
        model = self._make_model()
        allowed = {"department", "id", "name", "employeeCount"}
        _apply_column_group_filter(model, allowed)

        assert "id" in model.columns
        assert "name" in model.columns
        assert "email" not in model.columns

    def test_filter_removes_unreferenced_measures(self):
        model = self._make_model()
        allowed = {"department", "id", "employeeCount"}
        _apply_column_group_filter(model, allowed)

        assert "employeeCount" in model.measures
        assert "salary" not in model.measures

    def test_dollar_ref_keeps_base_dimension(self):
        """salesDate$year should keep the 'salesDate' dimension."""
        model = self._make_model()
        # Use dollar refs — base name 'department' should be extracted
        allowed = {"department$completeName", "id"}
        _apply_column_group_filter(model, allowed)

        assert "department" in model.dimensions
        assert "job" not in model.dimensions


class TestQmColumnGroupsIntegration:
    """Integration tests: load TM+QM from temp files, verify columnGroups filtering."""

    def test_qm_filters_dimensions_via_column_groups(self):
        """QM with columnGroups should only expose referenced dimensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "model"
            model_dir.mkdir()
            (model_dir / "EmpModel.tm").write_text(
                """
export const model = {
    name: 'EmpModel',
    caption: 'Employees',
    tableName: 'hr_employee',
    idColumn: 'id',
    dimensions: [
        { name: 'department', tableName: 'hr_dept', foreignKey: 'dept_id', primaryKey: 'id', captionColumn: 'name' },
        { name: 'job', tableName: 'hr_job', foreignKey: 'job_id', primaryKey: 'id', captionColumn: 'name' },
        { name: 'user', tableName: 'res_users', foreignKey: 'user_id', primaryKey: 'id', captionColumn: 'login' }
    ],
    properties: [
        { column: 'id', caption: 'ID', type: 'INTEGER' },
        { column: 'name', caption: 'Name', type: 'STRING' },
        { column: 'email', caption: 'Email', type: 'STRING' }
    ],
    measures: [
        { column: 'id', name: 'empCount', caption: 'Count', aggregation: 'COUNT_DISTINCT' }
    ]
};
""",
                encoding="utf-8",
            )
            query_dir = Path(tmpdir) / "query"
            query_dir.mkdir()
            (query_dir / "EmpQueryModel.qm").write_text(
                """
const emp = loadTableModel('EmpModel');
export const queryModel = {
    name: 'EmpQueryModel',
    caption: 'Employee Query',
    model: emp,
    columnGroups: [
        {
            caption: 'Info',
            items: [
                { ref: emp.id },
                { ref: emp.name }
            ]
        },
        {
            caption: 'Org',
            items: [
                { ref: emp.department },
                { ref: emp.job }
            ]
        },
        {
            caption: 'Metrics',
            items: [
                { ref: emp.empCount }
            ]
        }
    ]
};
""",
                encoding="utf-8",
            )

            models = load_models_from_directory(tmpdir)
            qm = next(m for m in models if m.name == "EmpQueryModel")

            # 'user' dimension should be filtered out
            assert "department" in qm.dimensions
            assert "job" in qm.dimensions
            assert "user" not in qm.dimensions

            # dimension_joins too
            join_names = {j.name for j in qm.dimension_joins}
            assert "department" in join_names
            assert "job" in join_names
            assert "user" not in join_names

            # columns: only id and name
            assert "id" in qm.columns
            assert "name" in qm.columns
            assert "email" not in qm.columns

            # measures
            assert "empCount" in qm.measures

    def test_qm_without_column_groups_keeps_all(self):
        """QM without columnGroups should expose all TM fields (backward compat)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "model"
            model_dir.mkdir()
            (model_dir / "SalesModel.tm").write_text(
                """
export const model = {
    name: 'SalesModel',
    caption: 'Sales',
    tableName: 'sales',
    idColumn: 'id',
    dimensions: [
        { name: 'product', tableName: 'dim_product', foreignKey: 'product_id', primaryKey: 'id', captionColumn: 'name' },
        { name: 'customer', tableName: 'dim_customer', foreignKey: 'customer_id', primaryKey: 'id', captionColumn: 'name' }
    ],
    measures: [
        { column: 'amount', name: 'amount', caption: 'Amount', aggregation: 'sum' }
    ]
};
""",
                encoding="utf-8",
            )
            query_dir = Path(tmpdir) / "query"
            query_dir.mkdir()
            (query_dir / "SalesQueryModel.qm").write_text(
                """
const s = loadTableModel('SalesModel');
export const queryModel = {
    name: 'SalesQueryModel',
    caption: 'Sales Query',
    model: s
};
""",
                encoding="utf-8",
            )

            models = load_models_from_directory(tmpdir)
            qm = next(m for m in models if m.name == "SalesQueryModel")

            # All TM dimensions should be present
            assert "product" in qm.dimensions
            assert "customer" in qm.dimensions
            assert "amount" in qm.measures

    def test_odoo_employee_qm_filters_user_dimension(self):
        """Integration: OdooHrEmployeeQueryModel should NOT expose 'user' dimension."""
        import os
        odoo_dir = os.path.join("src", "foggy", "demo", "models", "odoo")
        if not os.path.exists(odoo_dir):
            pytest.skip("Odoo demo models not found")

        models = load_models_from_directory(odoo_dir)
        tm = next(m for m in models if m.name == "OdooHrEmployeeModel")
        qm = next(m for m in models if m.name == "OdooHrEmployeeQueryModel")

        # TM should still have 'user' dimension
        assert "user" in tm.dimensions

        # QM should NOT have 'user' — it's excluded by columnGroups
        assert "user" not in qm.dimensions
        join_names = {j.name for j in qm.dimension_joins}
        assert "user" not in join_names

        # QM should still have the 5 referenced dimensions
        assert "department" in qm.dimensions
        assert "job" in qm.dimensions
        assert "company" in qm.dimensions
        assert "parent" in qm.dimensions
        assert "workLocation" in qm.dimensions

    def test_auto_expand_qm_root_dimension_properties_keep_distinct_alias_labels(self):
        """Python QM path resolves root dimension properties independently, without alias reuse."""
        ecommerce_dir = Path("src") / "foggy" / "demo" / "models" / "ecommerce"
        models = load_models_from_directory(str(ecommerce_dir))
        qm = next(m for m in models if m.name == "FactSalesAutoExpandQueryModel")

        product_fields = {
            "product$id": "商品(ID)",
            "product$caption": "商品",
            "product$productId": "商品ID",
            "product$brand": "品牌",
            "product$unitPrice": "商品售价",
        }

        resolved = {field: qm.resolve_field(field) for field in product_fields}

        assert all(info is not None for info in resolved.values())
        assert {field: info["alias_label"] for field, info in resolved.items()} == product_fields
        assert len({info["alias_label"] for info in resolved.values()}) == len(product_fields)

    def test_auto_expand_qm_does_not_load_nested_dimension_refs_yet(self):
        """Current Python loader filters root dims only and does not surface nested snowflake refs."""
        ecommerce_dir = Path("src") / "foggy" / "demo" / "models" / "ecommerce"
        models = load_models_from_directory(str(ecommerce_dir))
        qm = next(m for m in models if m.name == "FactSalesAutoExpandQueryModel")

        assert "product" in qm.dimensions
        assert "store" in qm.dimensions
        assert "productCategory" not in qm.dimensions
        assert "storeRegion" not in qm.dimensions

        assert qm.resolve_field("product.category$categoryId") is None
        assert qm.resolve_field("store.region$province") is None

    def test_multi_fact_join_qm_is_not_loaded_yet_for_order_payment(self, caplog):
        """Python loader does not support the V2 multi-fact JOIN QM path yet."""
        ecommerce_dir = Path("src") / "foggy" / "demo" / "models" / "ecommerce"

        with caplog.at_level("WARNING"):
            models = load_models_from_directory(str(ecommerce_dir))

        model_names = {m.name for m in models}
        assert "FactOrderModel" in model_names
        assert "FactPaymentModel" in model_names
        assert "OrderPaymentJoinQueryModel" not in model_names
        assert "Unknown dict method 'leftjoin'" in caplog.text

    def test_multi_fact_join_qm_is_not_loaded_yet_for_sales_return(self, caplog):
        """Python parser/evaluator still rejects chained JOIN.and(...) QM syntax."""
        ecommerce_dir = Path("src") / "foggy" / "demo" / "models" / "ecommerce"

        with caplog.at_level("WARNING"):
            models = load_models_from_directory(str(ecommerce_dir))

        model_names = {m.name for m in models}
        assert "FactSalesModel" in model_names
        assert "FactReturnModel" in model_names
        assert "SalesReturnJoinQueryModel" not in model_names
        assert "Expected IDENTIFIER, but got AND" in caplog.text
