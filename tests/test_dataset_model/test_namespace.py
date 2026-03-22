"""Tests for namespace support — aligned with Java @EnableFoggyFramework(namespace=...).

Covers:
- load_models_from_directory with namespace parameter
- SemanticQueryService namespace-aware register/get/unregister
- ModelDirectoryConfig (model_bundles config)
- Bare-name fallback lookup
- unregister_by_namespace
"""

import pytest
import tempfile
from pathlib import Path

from foggy.dataset_model.impl.loader import load_models_from_directory
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.impl.model import DbTableModelImpl, DbModelMeasureImpl
from foggy.dataset_model.definitions.base import AggregationType
from foggy.mcp.config.properties import ModelDirectoryConfig, McpProperties
from foggy.mcp_spi import SemanticQueryRequest


# ==================== ModelDirectoryConfig ====================


class TestModelDirectoryConfig:
    """Tests for the namespace-aware bundle config model."""

    def test_basic_config(self):
        cfg = ModelDirectoryConfig(path="/data/models/odoo", namespace="odoo")
        assert cfg.path == "/data/models/odoo"
        assert cfg.namespace == "odoo"

    def test_with_name_and_watch(self):
        cfg = ModelDirectoryConfig(
            path="/data/models", namespace="dev",
            name="openhands-models", watch=True,
        )
        assert cfg.name == "openhands-models"
        assert cfg.namespace == "dev"
        assert cfg.watch is True

    def test_no_namespace(self):
        cfg = ModelDirectoryConfig(path="./models")
        assert cfg.namespace is None

    def test_mcp_properties_model_bundles(self):
        props = McpProperties(
            model_bundles=[
                ModelDirectoryConfig(path="/odoo/models", namespace="odoo", name="odoo-bridge"),
                ModelDirectoryConfig(path="/wms/models", namespace="wms"),
            ]
        )
        assert len(props.model_bundles) == 2
        assert props.model_bundles[0].namespace == "odoo"
        assert props.model_bundles[1].namespace == "wms"

    def test_mcp_properties_backward_compatible(self):
        """model_directories (List[str]) still works."""
        props = McpProperties(model_directories=["/a", "/b"])
        assert props.model_directories == ["/a", "/b"]
        assert props.model_bundles == []


# ==================== load_models_from_directory with namespace ====================


class TestLoadModelsWithNamespace:
    """Tests for namespace prefix in load_models_from_directory."""

    @pytest.fixture
    def model_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_subdir = Path(tmpdir) / "model"
            model_subdir.mkdir()
            (model_subdir / "SalesModel.tm").write_text(
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
            (model_subdir / "OrderModel.tm").write_text(
                """
export const model = {
    name: 'OrderModel',
    caption: 'Orders',
    tableName: 'orders',
    idColumn: 'id'
};
""",
                encoding="utf-8",
            )
            query_subdir = Path(tmpdir) / "query"
            query_subdir.mkdir()
            (query_subdir / "SalesQueryModel.qm").write_text(
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
            yield tmpdir

    def test_no_namespace(self, model_dir):
        """Without namespace, models use bare names."""
        models = load_models_from_directory(model_dir)
        names = {m.name for m in models}
        assert "SalesModel" in names
        assert "OrderModel" in names
        assert "SalesQueryModel" in names

    def test_with_namespace(self, model_dir):
        """With namespace, all model names get prefix."""
        models = load_models_from_directory(model_dir, namespace="odoo")
        names = {m.name for m in models}
        assert "odoo:SalesModel" in names
        assert "odoo:OrderModel" in names
        assert "odoo:SalesQueryModel" in names

    def test_namespace_none_same_as_no_namespace(self, model_dir):
        models = load_models_from_directory(model_dir, namespace=None)
        names = {m.name for m in models}
        assert "SalesModel" in names  # no prefix

    def test_namespace_preserves_model_internals(self, model_dir):
        """Namespace only changes name, not source_table etc."""
        models = load_models_from_directory(model_dir, namespace="shop")
        sales = next(m for m in models if m.name == "shop:SalesModel")
        assert sales.source_table == "sales"
        assert "amount" in sales.measures


# ==================== SemanticQueryService namespace ====================


class TestSemanticQueryServiceNamespace:
    """Tests for namespace-aware registration and lookup."""

    def _make_model(self, name, table="t"):
        m = DbTableModelImpl(name=name, source_table=table)
        m.add_measure(DbModelMeasureImpl(
            name="count", column="id", aggregation=AggregationType.COUNT_DISTINCT,
        ))
        return m

    def test_register_with_namespace_param(self):
        svc = SemanticQueryService()
        model = self._make_model("SalesModel")
        svc.register_model(model, namespace="odoo")

        # Accessible by full name
        assert svc.get_model("odoo:SalesModel") is not None
        # Also accessible by bare name (fallback)
        assert svc.get_model("SalesModel") is not None

    def test_register_pre_namespaced(self):
        """Model with name already containing ':' is registered as-is."""
        svc = SemanticQueryService()
        model = self._make_model("ecommerce:FactSalesModel")
        svc.register_model(model)

        assert svc.get_model("ecommerce:FactSalesModel") is not None
        assert svc.get_model("FactSalesModel") is not None  # fallback

    def test_bare_name_not_overwritten(self):
        """If a bare name already exists, namespace registration doesn't overwrite it."""
        svc = SemanticQueryService()
        original = self._make_model("SalesModel", table="original_table")
        namespaced = self._make_model("SalesModel", table="ns_table")

        svc.register_model(original)  # registers as "SalesModel"
        svc.register_model(namespaced, namespace="odoo")  # registers as "odoo:SalesModel"

        # Bare name still points to original
        assert svc.get_model("SalesModel").source_table == "original_table"
        # Namespaced points to new
        assert svc.get_model("odoo:SalesModel").source_table == "ns_table"

    def test_unregister_by_namespace(self):
        svc = SemanticQueryService()
        svc.register_model(self._make_model("ModelA"), namespace="odoo")
        svc.register_model(self._make_model("ModelB"), namespace="odoo")
        svc.register_model(self._make_model("ModelC"), namespace="wms")

        removed = svc.unregister_by_namespace("odoo")
        assert removed == 2

        assert svc.get_model("odoo:ModelA") is None
        assert svc.get_model("odoo:ModelB") is None
        assert svc.get_model("wms:ModelC") is not None

    def test_unregister_by_namespace_empty(self):
        svc = SemanticQueryService()
        removed = svc.unregister_by_namespace("nonexistent")
        assert removed == 0

    def test_get_all_model_names_includes_namespaced(self):
        svc = SemanticQueryService()
        svc.register_model(self._make_model("A"), namespace="ns1")
        svc.register_model(self._make_model("B"))

        names = svc.get_all_model_names()
        assert "ns1:A" in names
        assert "B" in names

    def test_query_by_namespaced_name(self):
        """Can query using the full namespace:name."""
        svc = SemanticQueryService()
        model = self._make_model("SalesModel", table="sales")
        svc.register_model(model, namespace="odoo")

        r = svc.query_model(
            "odoo:SalesModel",
            SemanticQueryRequest(columns=["count"], limit=5),
            mode="validate",
        )
        assert r.error is None
        assert "sales" in r.sql

    def test_query_by_bare_name_fallback(self):
        """Can query using bare name when no conflict."""
        svc = SemanticQueryService()
        model = self._make_model("SalesModel", table="sales")
        svc.register_model(model, namespace="odoo")

        r = svc.query_model(
            "SalesModel",
            SemanticQueryRequest(columns=["count"], limit=5),
            mode="validate",
        )
        assert r.error is None
        assert "sales" in r.sql


# ==================== Integration: Odoo demo with namespace ====================


class TestOdooDemoNamespace:
    """Integration test: load Odoo demo models with namespace."""

    def test_odoo_namespace(self):
        import os
        odoo_dir = os.path.join("src", "foggy", "demo", "models", "odoo")
        if not os.path.exists(odoo_dir):
            pytest.skip("Odoo demo models not found")

        models = load_models_from_directory(odoo_dir, namespace="odoo")
        names = {m.name for m in models}

        # TMs have namespace prefix
        assert "odoo:OdooSaleOrderModel" in names
        assert "odoo:OdooHrEmployeeModel" in names

        # QMs have namespace prefix
        assert "odoo:OdooSaleOrderQueryModel" in names

        # Register and query by both namespaced and bare name
        svc = SemanticQueryService()
        for m in models:
            svc.register_model(m)

        # Full name works
        assert svc.get_model("odoo:OdooSaleOrderModel") is not None
        # Bare name fallback works
        assert svc.get_model("OdooSaleOrderModel") is not None

        r = svc.query_model(
            "odoo:OdooSaleOrderModel",
            SemanticQueryRequest(columns=["amountTotal"], limit=5),
            mode="validate",
        )
        assert r.error is None
        assert "amount_total" in r.sql
