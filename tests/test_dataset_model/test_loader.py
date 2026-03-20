"""
Unit tests for TM/QM loader module.
"""

import pytest
import tempfile
import os
from pathlib import Path

from foggy.dataset_model.impl.loader import (
    TableModelLoader,
    JdbcTableModelLoader,
    TableModelLoaderManager,
    ModelLoadContext,
    get_loader,
    init_loader,
)
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.dataset_model.definitions.base import DimensionType, ColumnType, AggregationType
from foggy.dataset_model.definitions.measure import MeasureType


class TestJdbcTableModelLoader:
    """Tests for JDBC table model loader."""

    def test_get_type_name(self):
        """Test loader type name."""
        loader = JdbcTableModelLoader()
        assert loader.get_type_name() == "jdbc"

    def test_load_basic_model(self):
        """Test loading a basic table model."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext(datasource="test_db")

        definition = {
            "name": "sales_order",
            "alias": "销售订单",
            "description": "销售订单表",
            "tableName": "t_sales_order",
            "schema": "public",
            "primaryKey": ["order_id"],
        }

        model = loader.load(definition, context)

        assert model.name == "sales_order"
        assert model.alias == "销售订单"
        assert model.source_table == "t_sales_order"
        assert model.source_schema == "public"
        assert "order_id" in model.primary_key

    def test_load_model_with_dimensions(self):
        """Test loading model with dimensions."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext()

        definition = {
            "name": "test_model",
            "tableName": "test_table",
            "dimensions": [
                {
                    "name": "product_name",
                    "column": "product_name",
                    "type": "string",
                    "alias": "产品名称",
                },
                {
                    "name": "order_date",
                    "column": "order_date",
                    "type": "datetime",
                    "alias": "订单日期",
                },
                {
                    "name": "category",
                    "column": "category_id",
                    "tableName": "dim_category",
                    "alias": "分类",
                },
            ],
        }

        model = loader.load(definition, context)

        assert len(model.dimensions) == 3
        assert "product_name" in model.dimensions
        assert model.dimensions["product_name"].dimension_type == DimensionType.REGULAR
        assert model.dimensions["order_date"].dimension_type == DimensionType.TIME

    def test_load_model_with_measures(self):
        """Test loading model with measures."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext()

        definition = {
            "name": "test_model",
            "tableName": "test_table",
            "measures": [
                {
                    "name": "total_amount",
                    "column": "amount",
                    "aggregation": "sum",
                    "alias": "总金额",
                },
                {
                    "name": "order_count",
                    "column": "order_id",
                    "aggregation": "count",
                    "alias": "订单数",
                },
                {
                    "name": "avg_price",
                    "expression": "total_amount / order_count",
                    "alias": "平均单价",
                },
            ],
        }

        model = loader.load(definition, context)

        assert len(model.measures) == 3
        assert model.measures["total_amount"].aggregation == AggregationType.SUM
        assert model.measures["avg_price"].measure_type == MeasureType.CALCULATED

    def test_load_model_with_properties(self):
        """Test loading model with properties."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext()

        definition = {
            "name": "test_model",
            "tableName": "test_table",
            "properties": [
                {"name": "created_at", "type": "datetime", "nullable": False},
                {"name": "updated_at", "type": "datetime"},
                {"name": "status", "type": "string"},
            ],
        }

        model = loader.load(definition, context)

        assert len(model.columns) == 3
        assert "created_at" in model.columns
        assert model.columns["created_at"].column_type == ColumnType.DATETIME

    def test_hierarchical_dimension(self):
        """Test loading hierarchical dimension."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext()

        definition = {
            "name": "test_model",
            "tableName": "test_table",
            "dimensions": [
                {
                    "name": "org",
                    "column": "org_id",
                    "parentKey": "parent_id",
                    "childKey": "org_id",
                    "closureTableName": "org_closure",
                },
            ],
        }

        model = loader.load(definition, context)

        assert model.dimensions["org"].is_hierarchical
        assert model.dimensions["org"].dimension_type == DimensionType.HIERARCHY
        assert model.dimensions["org"].hierarchy_table == "org_closure"

    def test_parse_column_type(self):
        """Test column type parsing."""
        loader = JdbcTableModelLoader()

        assert loader._parse_column_type("string") == ColumnType.STRING
        assert loader._parse_column_type("VARCHAR") == ColumnType.STRING
        assert loader._parse_column_type("int") == ColumnType.INTEGER
        assert loader._parse_column_type("BIGINT") == ColumnType.LONG
        assert loader._parse_column_type("datetime") == ColumnType.DATETIME
        assert loader._parse_column_type("unknown") == ColumnType.STRING


class TestTableModelLoaderManager:
    """Tests for table model loader manager."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create temporary model directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a TM file
            tm_content = """
name: test_sales
alias: 测试销售
description: 测试销售订单表
tableName: t_sales_order
schema: public
primaryKey:
  - order_id
dimensions:
  - name: product_name
    column: product_name
    type: string
    alias: 产品名称
measures:
  - name: total_amount
    column: amount
    aggregation: sum
    alias: 总金额
"""
            tm_file = Path(tmpdir) / "test_sales.tm.yaml"
            tm_file.write_text(tm_content, encoding="utf-8")

            # Create a QM file
            qm_content = """
name: sales_query
alias: 销售查询
description: 销售数据查询
tableModel: test_sales
"""
            qm_file = Path(tmpdir) / "sales_query.qm.yaml"
            qm_file.write_text(qm_content, encoding="utf-8")

            yield tmpdir

    def test_init_loader(self):
        """Test loader initialization."""
        manager = TableModelLoaderManager()
        assert "jdbc" in manager._loaders

    def test_load_yaml_model(self, temp_model_dir):
        """Test loading model from YAML file."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        model = manager.load_model("test_sales")

        assert model.name == "test_sales"
        assert model.alias == "测试销售"
        assert model.source_table == "t_sales_order"
        assert "product_name" in model.dimensions
        assert "total_amount" in model.measures

    def test_load_query_model(self, temp_model_dir):
        """Test loading query model."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        qm = manager.load_query_model("sales_query")

        assert qm.name == "sales_query"
        assert qm.table_model == "test_sales"

    def test_model_caching(self, temp_model_dir):
        """Test model caching."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        model1 = manager.load_model("test_sales")
        model2 = manager.load_model("test_sales")

        assert model1 is model2

    def test_clear_cache(self, temp_model_dir):
        """Test cache clearing."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        manager.load_model("test_sales")
        assert "test_sales" in manager.list_models()

        manager.clear_cache()
        assert len(manager.list_models()) == 0

    def test_namespace_support(self, temp_model_dir):
        """Test namespace support."""
        # Create namespace subdirectory
        ns_dir = Path(temp_model_dir) / "myapp"
        ns_dir.mkdir()

        ns_content = """
name: orders
tableName: app_orders
"""
        ns_file = ns_dir / "orders.tm.yaml"
        ns_file.write_text(ns_content, encoding="utf-8")

        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        model = manager.load_model("orders", namespace="myapp")

        assert model.name == "orders"
        assert "myapp:orders" in manager.list_models()

    def test_model_not_found(self, temp_model_dir):
        """Test model not found error."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        with pytest.raises(FileNotFoundError):
            manager.load_model("nonexistent")

    def test_get_model(self, temp_model_dir):
        """Test get model without loading."""
        manager = TableModelLoaderManager(model_dirs=[temp_model_dir])

        # Not loaded yet
        assert manager.get_model("test_sales") is None

        # Load it
        manager.load_model("test_sales")

        # Now get should work
        model = manager.get_model("test_sales")
        assert model is not None


class TestGlobalLoader:
    """Tests for global loader functions."""

    def test_get_loader(self):
        """Test get_loader returns singleton."""
        from foggy.dataset_model.impl.loader import _global_loader

        # Reset global loader
        import foggy.dataset_model.impl.loader as loader_module
        loader_module._global_loader = None

        loader1 = get_loader()
        loader2 = get_loader()

        assert loader1 is loader2

    def test_init_loader(self):
        """Test init_loader creates new instance."""
        import foggy.dataset_model.impl.loader as loader_module
        loader_module._global_loader = None

        loader = init_loader(model_dirs=["/tmp/models"])

        assert loader is not None
        assert "/tmp/models" in loader._model_dirs


class TestModelValidation:
    """Tests for model validation during loading."""

    def test_validation_success(self):
        """Test successful validation."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext(validate_on_load=True, fail_on_error=True)

        definition = {
            "name": "valid_model",
            "tableName": "valid_table",
            "dimensions": [
                {"name": "dim1", "column": "col1"},
            ],
            "measures": [
                {"name": "m1", "column": "col2", "aggregation": "sum"},
            ],
        }

        # Should not raise
        model = loader.load(definition, context)
        assert model.valid

    def test_validation_warning_only(self):
        """Test validation warning without failure."""
        loader = JdbcTableModelLoader()
        context = ModelLoadContext(validate_on_load=True, fail_on_error=False)

        definition = {
            "name": "test_model",
            "tableName": "test_table",
            "measures": [
                # Calculated measure without expression - validation issue
                {"name": "bad_measure", "type": "calculated"},
            ],
        }

        # Should not raise because fail_on_error is False
        model = loader.load(definition, context)
        # Model should still be created
        assert model.name == "test_model"