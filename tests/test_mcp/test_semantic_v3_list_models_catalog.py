from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.mcp.routers.semantic_v3 import create_semantic_v3_router
from foggy.mcp_spi.semantic import DeniedColumn


class _CatalogService:
    def __init__(self):
        self.calls = []

    def get_model_catalog(
        self,
        model_names=None,
        visible_fields=None,
        denied_columns=None,
        llm_hints=None,
        field_limit=10,
    ):
        self.calls.append({
            "model_names": model_names,
            "visible_fields": visible_fields,
            "denied_columns": denied_columns,
            "llm_hints": llm_hints,
            "field_limit": field_limit,
        })
        item = {
            "model": "OdooResCompanyQueryModel",
            "caption": "Company Directory",
            "description": "Companies",
            "namespace": "odoo",
            "physicalTables": ["res_company"],
            "recommendedNext": "dataset.describe_model_internal",
        }
        if field_limit > 0:
            item["fieldPreview"] = ["id"]
            item["fieldCount"] = 1
        return {
            "models": ["OdooResCompanyQueryModel"],
            "count": 1,
            "recommendedNext": "dataset.describe_model_internal",
            "items": [item],
        }

    @staticmethod
    def render_model_catalog_markdown(catalog):
        return "\n".join(item["model"] for item in catalog.get("items", []))


def _client(service):
    app = FastAPI()
    app.include_router(create_semantic_v3_router(semantic_service=service), prefix="/semantic/v3")
    return TestClient(app)


def test_post_list_models_catalog_accepts_host_arguments_and_returns_markdown():
    service = _CatalogService()
    client = _client(service)

    response = client.post(
        "/semantic/v3/list-models",
        json={
            "format": "markdown",
            "modelNames": ["OdooResCompanyQueryModel"],
            "visibleFields": ["id"],
            "deniedColumns": [{"table": "res_company", "columns": ["secret_code"]}],
            "fieldLimit": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "markdown"
    assert body["content"] == "OdooResCompanyQueryModel"
    assert "data" not in body
    assert "items" not in body
    assert service.calls == [{
        "model_names": ["OdooResCompanyQueryModel"],
        "visible_fields": ["id"],
        "denied_columns": [DeniedColumn(table="res_company", column="secret_code")],
        "llm_hints": None,
        "field_limit": 20,
    }]


def test_post_list_models_catalog_defaults_to_json():
    service = _CatalogService()
    client = _client(service)

    response = client.post("/semantic/v3/list-models", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "json"
    assert body["data"]["count"] == 1
    assert "OdooResCompanyQueryModel" in body["content"]
    assert service.calls[0]["field_limit"] == 10


def test_post_list_models_json_field_limit_zero_omits_field_details():
    service = _CatalogService()
    client = _client(service)

    response = client.post(
        "/semantic/v3/list-models",
        json={"format": "json", "fieldLimit": 0},
    )

    assert response.status_code == 200
    body = response.json()
    item = body["data"]["items"][0]
    assert "fields" not in item
    assert "fieldPreview" not in item
    assert "fieldCount" not in item
    assert "primaryTimeField" not in item
    assert service.calls[0]["field_limit"] == 0


def test_post_list_models_all_returns_markdown_and_catalog_without_field_details():
    service = _CatalogService()
    client = _client(service)

    response = client.post(
        "/semantic/v3/list-models",
        json={"format": "all", "fieldLimit": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "all"
    assert body["content"] == "OdooResCompanyQueryModel"
    assert body["data"]["count"] == 1
    item = body["data"]["items"][0]
    assert item["model"] == "OdooResCompanyQueryModel"
    assert "fields" not in item
    assert "fieldPreview" not in item
    assert "fieldCount" not in item
    assert "primaryTimeField" not in item
    assert service.calls[0]["field_limit"] == 0
