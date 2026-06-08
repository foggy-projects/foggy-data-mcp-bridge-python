"""Runtime dictionary discovery metadata parity tests."""

import pytest

from foggy.dataset_model.definitions.base import ColumnType, DbColumnDef
from foggy.dataset_model.impl.loader import JdbcTableModelLoader, ModelLoadContext
from foggy.dataset_model.impl.model import DbTableModelImpl
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.mcp_spi import SemanticQueryRequest, SemanticQueryResponse, SemanticRequestContext


class _FakeDiscoveryService(SemanticQueryService):
    def __init__(self, rows=None, error=None):
        super().__init__(enable_cache=False)
        self.rows = rows or []
        self.error = error
        self.calls = []

    def query_model(
        self,
        model: str,
        request: SemanticQueryRequest,
        mode: str = "execute",
        context=None,
    ) -> SemanticQueryResponse:
        self.calls.append((model, request, mode, context))
        if self.error:
            return SemanticQueryResponse.from_error(self.error)
        return SemanticQueryResponse.from_legacy(data=list(self.rows), total=len(self.rows))


def _make_model(discovery) -> DbTableModelImpl:
    model = DbTableModelImpl(
        name="SaleOrder",
        alias="Sale Order",
        description="Order model",
        source_table="sale_order",
    )
    model.columns["status"] = DbColumnDef(
        name="status",
        alias="Status",
        column_type=ColumnType.STRING,
        comment="Order lifecycle status",
        dictionaryDiscovery=discovery,
    )
    return model


def test_json_metadata_includes_runtime_dictionary_discovery():
    service = _FakeDiscoveryService(
        rows=[
            {"status": "pending_approval", "__foggyDictionaryCount": 4},
            {"status": "processing", "__foggyDictionaryCount": 2},
            {"status": "cancelled", "__foggyDictionaryCount": 1},
        ],
    )
    service.register_model(
        _make_model(
            {
                "enabled": True,
                "maxValues": 2,
                "aliases": {
                    "open_order": {
                        "values": ["pending_approval", "processing"],
                        "description": "Orders still being handled",
                    },
                },
            },
        )
    )

    metadata = service.get_metadata_v3(model_names=["SaleOrder"])

    discovery = metadata["fields"]["status"]["dictionaryDiscovery"]
    assert discovery["valuesStatus"] == "sampled"
    assert discovery["strategy"] == "group_by"
    assert discovery["truncated"] is True
    assert discovery["values"] == [
        {"value": "pending_approval", "count": 4},
        {"value": "processing", "count": 2},
    ]
    assert discovery["aliases"]["open_order"]["values"] == [
        "pending_approval",
        "processing",
    ]

    assert len(service.calls) == 1
    model_name, request, mode, context = service.calls[0]
    assert model_name == "SaleOrder"
    assert mode == "execute"
    assert context is None
    assert request.columns == ["status", "COUNT(status) AS __foggyDictionaryCount"]
    assert request.group_by == ["status"]
    assert request.order_by == [{"field": "__foggyDictionaryCount", "dir": "desc"}]
    assert request.limit == 3
    assert request.return_total is False


def test_sensitive_dictionary_discovery_not_exposed_and_not_queried():
    service = _FakeDiscoveryService(rows=[{"status": "draft", "__foggyDictionaryCount": 9}])
    service.register_model(
        _make_model({"enabled": True, "sensitive": True, "maxValues": 5})
    )

    metadata = service.get_metadata_v3(model_names=["SaleOrder"])

    discovery = metadata["fields"]["status"]["dictionaryDiscovery"]
    assert discovery["valuesStatus"] == "not_exposed"
    assert "values" not in discovery
    assert service.calls == []


def test_dictionary_discovery_failure_uses_generic_error():
    service = _FakeDiscoveryService(error="physical table sale_order missing")
    service.register_model(_make_model({"enabled": True, "maxValues": 5}))

    metadata = service.get_metadata_v3(model_names=["SaleOrder"])

    discovery = metadata["fields"]["status"]["dictionaryDiscovery"]
    assert discovery["valuesStatus"] == "failed"
    assert discovery["error"] == "runtime dictionary discovery failed"
    assert "physical table sale_order missing" not in str(metadata)


def test_hidden_dictionary_discovery_field_is_not_queried():
    service = _FakeDiscoveryService(rows=[{"status": "draft", "__foggyDictionaryCount": 9}])
    service.register_model(_make_model({"enabled": True, "maxValues": 5}))

    metadata = service.get_metadata_v3(
        model_names=["SaleOrder"],
        visible_fields=["id"],
    )

    assert "status" not in metadata["fields"]
    assert service.calls == []


def test_dictionary_discovery_cache_is_context_scoped():
    service = _FakeDiscoveryService(rows=[{"status": "draft", "__foggyDictionaryCount": 9}])
    service.register_model(_make_model({"enabled": True, "maxValues": 5, "refreshTtlSeconds": 60}))

    cn_context = SemanticRequestContext(namespace="cn")
    us_context = SemanticRequestContext(namespace="us")

    service.get_metadata_v3(model_names=["SaleOrder"], context=cn_context)
    service.get_metadata_v3(model_names=["SaleOrder"], context=cn_context)
    service.get_metadata_v3(model_names=["SaleOrder"], context=us_context)

    assert len(service.calls) == 2
    assert service.calls[0][3] is cn_context
    assert service.calls[1][3] is us_context


def test_markdown_includes_runtime_dictionary_values_and_aliases():
    service = _FakeDiscoveryService(
        rows=[
            {"status": "pending_approval", "__foggyDictionaryCount": 4},
            {"status": "processing", "__foggyDictionaryCount": 2},
        ],
    )
    service.register_model(
        _make_model(
            {
                "enabled": True,
                "maxValues": 10,
                "aliases": {
                    "open_order": {"values": ["pending_approval", "processing"]},
                },
            },
        )
    )

    markdown = service.get_metadata_v3_markdown(model_names=["SaleOrder"])

    assert "运行时字典发现" in markdown
    assert "pending_approval(4)" in markdown
    assert "processing(2)" in markdown
    assert "open_order" in markdown


def test_loader_dictionary_discovery_invalid_max_values_fails_closed():
    definition = {
        "name": "BadModel",
        "type": "jdbc",
        "tableName": "bad_table",
        "properties": [
            {
                "name": "status",
                "column": "status",
                "dictionaryDiscovery": {"enabled": True, "maxValues": 0},
            }
        ],
    }

    with pytest.raises(ValueError, match="dictionaryDiscovery.maxValues"):
        JdbcTableModelLoader().load(
            definition,
            ModelLoadContext(validate_on_load=False, fail_on_error=True),
        )
