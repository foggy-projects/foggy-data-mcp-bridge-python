import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.mcp.routers.mcp_rpc import create_mcp_router


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


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(
        create_mcp_router(semantic_service=_FakeSemanticService(), accessor=object()),
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
