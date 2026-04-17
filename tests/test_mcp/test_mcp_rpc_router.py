import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.mcp.routers.mcp_rpc import create_mcp_router
from foggy.mcp_spi.semantic import DeniedColumn
from foggy.mcp_spi import SemanticQueryResponse


class _FakeSemanticService:
    def __init__(self):
        self.metadata_v3_calls = []
        self.metadata_markdown_calls = []

    def get_metadata_v3(self, model_names=None, visible_fields=None, denied_columns=None):
        self.metadata_v3_calls.append({
            "model_names": model_names,
            "visible_fields": visible_fields,
            "denied_columns": denied_columns,
        })
        assert model_names == ["OdooResCompanyQueryModel"]
        return {
            "fields": {
                "id": {
                    "fieldName": "id",
                    "sourceColumn": "id",
                },
                "name": {
                    "fieldName": "name",
                    "sourceColumn": "name",
                },
            },
            "models": {
                "OdooResCompanyQueryModel": {
                    "factTable": "res_company",
                }
            },
        }

    def get_metadata_v3_markdown(self, model_names=None, visible_fields=None, denied_columns=None):
        self.metadata_markdown_calls.append({
            "model_names": model_names,
            "visible_fields": visible_fields,
            "denied_columns": denied_columns,
        })
        assert model_names == ["OdooResCompanyQueryModel"]
        return "# OdooResCompanyQueryModel - Company Directory"


class _FakeAccessor:
    def __init__(self, response: SemanticQueryResponse | None = None):
        self.response = response or SemanticQueryResponse(items=[])
        self.calls = []

    def query_model(self, model, payload, mode="execute"):
        self.calls.append({
            "model": model,
            "payload": payload,
            "mode": mode,
        })
        return self.response


def _make_client(accessor=None, semantic_service=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_mcp_router(
            semantic_service=semantic_service or _FakeSemanticService(),
            accessor=accessor or _FakeAccessor(),
        ),
        prefix="/mcp/analyst",
    )
    return TestClient(app)


def test_describe_model_internal_supports_json_format():
    client = _make_client()

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.describe_model_internal",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "format": "json",
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    text = body["result"]["content"][0]["text"]
    payload = json.loads(text)
    assert payload["fields"]["id"]["sourceColumn"] == "id"
    assert payload["models"]["OdooResCompanyQueryModel"]["factTable"] == "res_company"


def test_describe_model_internal_defaults_to_markdown():
    client = _make_client()

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.describe_model_internal",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["content"][0]["text"].startswith("# OdooResCompanyQueryModel")


def test_describe_model_internal_forwards_denied_columns_to_metadata_service():
    service = _FakeSemanticService()
    client = _make_client(semantic_service=service)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.describe_model_internal",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "format": "json",
                    "deniedColumns": [{"table": "res_company", "column": "name"}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert all(isinstance(item, DeniedColumn) for item in service.metadata_v3_calls[0]["denied_columns"])
    assert service.metadata_v3_calls == [{
        "model_names": ["OdooResCompanyQueryModel"],
        "visible_fields": None,
        "denied_columns": [DeniedColumn(table="res_company", column="name")],
    }]


def test_get_metadata_forwards_visible_fields_and_denied_columns():
    service = _FakeSemanticService()
    client = _make_client(semantic_service=service)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.get_metadata",
                "arguments": {
                    "format": "markdown",
                    "visibleFields": ["name"],
                    "deniedColumns": [{"table": "res_company", "column": "secret_code"}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert all(isinstance(item, DeniedColumn) for item in service.metadata_markdown_calls[0]["denied_columns"])
    assert service.metadata_markdown_calls == [{
        "model_names": None,
        "visible_fields": ["name"],
        "denied_columns": [DeniedColumn(table="res_company", column="secret_code")],
    }]


def test_get_metadata_expands_grouped_denied_columns():
    service = _FakeSemanticService()
    client = _make_client(semantic_service=service)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.get_metadata",
                "arguments": {
                    "format": "json",
                    "deniedColumns": [{"table": "res_company", "columns": ["name", "secret_code"]}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert all(isinstance(item, DeniedColumn) for item in service.metadata_v3_calls[0]["denied_columns"])
    assert service.metadata_v3_calls == [{
        "model_names": None,
        "visible_fields": None,
        "denied_columns": [
            DeniedColumn(table="res_company", column="name"),
            DeniedColumn(table="res_company", column="secret_code"),
        ],
    }]


def test_query_model_success_returns_result_status_success():
    accessor = _FakeAccessor(
        SemanticQueryResponse.from_legacy(
            data=[{"id": 1, "name": "Acme"}],
            columns_info=[{"name": "id", "dataType": "INTEGER"}],
            total=1,
            sql="SELECT 1",
        )
    )
    client = _make_client(accessor=accessor)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.query_model",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "payload": {"columns": ["id", "name"]},
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "success"
    payload = json.loads(body["result"]["content"][0]["text"])
    assert payload["items"] == [{"id": 1, "name": "Acme"}]
    assert accessor.calls == [{
        "model": "OdooResCompanyQueryModel",
        "payload": {"columns": ["id", "name"]},
        "mode": "execute",
    }]


def test_query_model_merges_top_level_governance_into_payload():
    accessor = _FakeAccessor(
        SemanticQueryResponse.from_legacy(
            data=[],
            columns_info=[{"name": "id", "dataType": "INTEGER"}],
            total=0,
            sql="SELECT 1",
        )
    )
    client = _make_client(accessor=accessor)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.query_model",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "payload": {"columns": ["id"]},
                    "deniedColumns": [{"table": "res_company", "column": "name"}],
                    "systemSlice": [{"field": "company_id", "op": "eq", "value": 1}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert accessor.calls == [{
        "model": "OdooResCompanyQueryModel",
        "payload": {
            "columns": ["id"],
            "deniedColumns": [{"table": "res_company", "column": "name"}],
            "systemSlice": [{"field": "company_id", "op": "eq", "value": 1}],
        },
        "mode": "execute",
    }]


def test_query_model_expands_grouped_denied_columns_before_forwarding():
    accessor = _FakeAccessor(
        SemanticQueryResponse.from_legacy(
            data=[],
            columns_info=[{"name": "id", "dataType": "INTEGER"}],
            total=0,
            sql="SELECT 1",
        )
    )
    client = _make_client(accessor=accessor)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.query_model",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "payload": {"columns": ["id"]},
                    "deniedColumns": [{"table": "res_company", "columns": ["name", "secret_code"]}],
                },
            },
        },
    )

    assert response.status_code == 200
    assert accessor.calls == [{
        "model": "OdooResCompanyQueryModel",
        "payload": {
            "columns": ["id"],
            "deniedColumns": [
                {"table": "res_company", "column": "name"},
                {"table": "res_company", "column": "secret_code"},
            ],
        },
        "mode": "execute",
    }]


def test_query_model_business_failure_returns_failed_status_without_jsonrpc_error():
    accessor = _FakeAccessor(
        SemanticQueryResponse.from_error('查询被拒绝：column "totalamount" does not exist')
    )
    client = _make_client(accessor=accessor)

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.query_model",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                    "payload": {"columns": ["totalAmount"]},
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["result"]["status"] == "failed"
    assert body["result"]["content"][0]["text"] == '查询被拒绝：column "totalamount" does not exist'


def test_query_model_missing_payload_still_uses_top_level_jsonrpc_error():
    client = _make_client()

    response = client.post(
        "/mcp/analyst/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "dataset.query_model",
                "arguments": {
                    "model": "OdooResCompanyQueryModel",
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error"]["code"] == -32602
    assert body["error"]["message"] == "payload parameter required"
    assert "result" not in body
