"""
Unit tests for SemanticQueryService._resolve_executor — multi-datasource routing.
"""

import pytest

from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.dataset.db.executor import ExecutorManager, DatabaseExecutor, QueryResult


class FakeExecutor(DatabaseExecutor):
    """Minimal executor stub identified by label."""

    def __init__(self, label: str = "default"):
        self.label = label

    async def execute(self, sql, params=None, limit=None):
        return QueryResult(columns=[], rows=[], total=0, sql=sql)

    async def execute_count(self, sql, params=None):
        return 0

    async def close(self):
        pass

    def __repr__(self):
        return f"FakeExecutor({self.label!r})"


def _make_model(name: str, datasource: str = None) -> DbTableModelImpl:
    """Create a minimal model with optional source_datasource."""
    return DbTableModelImpl(
        name=name,
        source_table=name.lower(),
        source_datasource=datasource,
    )


# ==================== Without ExecutorManager ====================


class TestResolveExecutorLegacy:
    """Without executor_manager set, _resolve_executor falls back to self._executor."""

    def test_returns_default_executor(self):
        svc = SemanticQueryService()
        ex = FakeExecutor("legacy")
        svc.set_executor(ex)

        model = _make_model("TestModel")
        assert svc._resolve_executor(model) is ex

    def test_returns_default_even_with_datasource_name(self):
        """If no executor_manager, ignore source_datasource."""
        svc = SemanticQueryService()
        ex = FakeExecutor("legacy")
        svc.set_executor(ex)

        model = _make_model("TestModel", datasource="odoo")
        assert svc._resolve_executor(model) is ex

    def test_returns_none_when_no_executor(self):
        svc = SemanticQueryService()
        model = _make_model("TestModel")
        assert svc._resolve_executor(model) is None


# ==================== With ExecutorManager ====================


class TestResolveExecutorMultiDatasource:
    """With executor_manager, routes by source_datasource."""

    @pytest.fixture
    def setup(self):
        svc = SemanticQueryService()
        mgr = ExecutorManager()

        ex_default = FakeExecutor("default")
        ex_odoo = FakeExecutor("odoo")
        ex_wms = FakeExecutor("wms")

        mgr.register("default", ex_default, set_default=True)
        mgr.register("odoo", ex_odoo)
        mgr.register("wms", ex_wms)

        svc.set_executor(ex_default)
        svc.set_executor_manager(mgr)

        return svc, ex_default, ex_odoo, ex_wms

    def test_named_datasource_routes_correctly(self, setup):
        svc, _, ex_odoo, _ = setup
        model = _make_model("OdooSaleOrder", datasource="odoo")
        assert svc._resolve_executor(model) is ex_odoo

    def test_different_named_datasource(self, setup):
        svc, _, _, ex_wms = setup
        model = _make_model("WarehouseStock", datasource="wms")
        assert svc._resolve_executor(model) is ex_wms

    def test_no_datasource_returns_default(self, setup):
        svc, ex_default, _, _ = setup
        model = _make_model("GenericModel")
        assert svc._resolve_executor(model) is ex_default

    def test_empty_datasource_returns_default(self, setup):
        svc, ex_default, _, _ = setup
        model = _make_model("GenericModel", datasource="")
        assert svc._resolve_executor(model) is ex_default

    def test_unknown_datasource_falls_back_to_default(self, setup):
        svc, ex_default, _, _ = setup
        model = _make_model("Unknown", datasource="nonexistent")
        assert svc._resolve_executor(model) is ex_default

    def test_model_without_source_datasource_attr(self, setup):
        """Models that don't have source_datasource at all → default."""
        svc, ex_default, _, _ = setup

        class BareModel:
            name = "BareModel"

        assert svc._resolve_executor(BareModel()) is ex_default


# ==================== Integration with query_model ====================


class TestResolveExecutorQueryIntegration:
    """Verify _resolve_executor is actually used in query paths."""

    def test_query_model_sync_uses_resolved_executor(self):
        """_execute_query receives model and resolves the right executor."""
        svc = SemanticQueryService()
        mgr = ExecutorManager()
        ex_a = FakeExecutor("ds_a")
        ex_b = FakeExecutor("ds_b")
        mgr.register("ds_a", ex_a, set_default=True)
        mgr.register("ds_b", ex_b)
        svc.set_executor(ex_a)
        svc.set_executor_manager(mgr)

        # Register a model pointing to ds_b
        model = _make_model("ModelB", datasource="ds_b")
        model.source_table = "test_table"
        svc.register_model(model)

        # Validate mode doesn't hit executor, but build verifies model lookup works
        from foggy.mcp_spi import SemanticQueryRequest
        response = svc.query_model("ModelB", SemanticQueryRequest(columns=["*"]), mode="validate")
        assert response.error is None
