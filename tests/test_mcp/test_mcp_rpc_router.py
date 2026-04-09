import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.mcp.routers.mcp_rpc import create_mcp_router
from foggy.mcp_spi import SemanticQueryResponse


class _FakeSemanticService:
    def get_metadata_v3(self, model_names=None):
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

    def get_metadata_v3_markdown(self, model_names=None):
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


def _make_client(accessor=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_mcp_router(
            semantic_service=_FakeSemanticService(),
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
