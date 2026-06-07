from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.mcp.routers.runtime_api_v1 import create_runtime_api_v1_router
from foggy.mcp_spi import SemanticQueryResponse


class _FakeSemanticService:
    def __init__(self):
        self.describe_calls = []
        self.registered = []
        self.unregistered_namespaces = []
        self.cache_invalidations = 0

    def get_all_model_names(self):
        return ["FactOrderQueryModel", *self.registered]

    def get_metadata_v3(self, model_names=None):
        self.describe_calls.append({"model_names": model_names})
        return {
            "models": {
                "FactOrderQueryModel": {
                    "fields": {
                        "orderId": {"fieldName": "orderId"},
                        "payAmount": {"fieldName": "payAmount"},
                    }
                }
            }
        }

    def register_model(self, model, namespace=None):
        name = getattr(model, "name", None)
        self.registered.append(f"{namespace}:{name}" if namespace else name)

    def unregister_by_namespace(self, namespace):
        self.unregistered_namespaces.append(namespace)
        return 0

    def invalidate_model_cache(self):
        self.cache_invalidations += 1


class _FakeAccessor:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def query_model_async(self, model, payload, mode="execute"):
        self.calls.append({"model": model, "payload": payload, "mode": mode})
        return self.response


class _FakeExecutor:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = []

    async def execute(self, sql, params=None):
        self.calls.append({"sql": sql, "params": params})
        return SimpleNamespace(rows=self.rows, error=self.error, sql=sql)


class _FakeExecutorManager:
    def __init__(self, executor):
        self.executor = executor
        self.calls = []

    def get(self, name=None):
        self.calls.append(name)
        return self.executor


class _FakeDataSourceManager:
    def __init__(self, config):
        self.config = config
        self.calls = []

    def get(self, name=None):
        self.calls.append(name)
        return self.config


def _client(accessor=None, semantic_service=None, state=None):
    app = FastAPI()
    if state:
        router = create_runtime_api_v1_router(state_getter=lambda: state)
    else:
        router = create_runtime_api_v1_router(
            semantic_service=semantic_service or _FakeSemanticService(),
            accessor=accessor or _FakeAccessor(SemanticQueryResponse(items=[])),
        )
    app.include_router(
        router,
        prefix="/api/v1",
    )
    return TestClient(app)


def test_capabilities_returns_runtime_envelope_and_honest_unsupported_states():
    client = _client()

    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["engine"] == "python"
    assert body["runtimeApiVersion"] == "foggy-runtime-api/v1"
    assert body["data"]["engine"] == body["engine"]
    assert body["data"]["runtimeApiVersion"] == body["runtimeApiVersion"]
    assert body["data"]["schemaVersion"] == "2026-06-06"
    assert body["data"]["enabled"] is True
    assert body["data"]["securityMode"] == "none-dev-test-only"
    assert body["diagnostics"] == {"warnings": []}
    assert body["error"] is None
    assert body["data"]["capabilities"]["runtime.capabilities"] == "supported"
    assert body["data"]["capabilities"]["query.validate"] == "supported"
    assert body["data"]["capabilities"]["models.validate"] == "supported"
    assert body["data"]["capabilities"]["models.refresh"] == "supported"
    assert body["data"]["capabilities"]["tables.inspect"] == "supported"


def test_models_list_and_describe_use_runtime_envelope():
    service = _FakeSemanticService()
    client = _client(semantic_service=service)

    models = client.get("/api/v1/models").json()
    describe = client.post("/api/v1/models/FactOrderQueryModel/describe", json={}).json()

    assert models["success"] is True
    assert models["data"] == {"models": ["FactOrderQueryModel"], "count": 1}
    assert describe["success"] is True
    assert describe["data"]["format"] == "json"
    assert "FactOrderQueryModel" in describe["data"]["data"]["models"]
    assert service.describe_calls == [{"model_names": ["FactOrderQueryModel"]}]


def test_query_validate_success_wraps_semantic_response():
    accessor = _FakeAccessor(SemanticQueryResponse(items=[]))
    client = _client(accessor=accessor)

    response = client.post(
        "/api/v1/query/FactOrderQueryModel/validate",
        json={"limit": 3, "columns": ["orderId", "payAmount"]},
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["items"] == []
    assert accessor.calls == [{
        "model": "FactOrderQueryModel",
        "payload": {"limit": 3, "columns": ["orderId", "payAmount"]},
        "mode": "validate",
    }]


def test_query_validate_bad_field_returns_structured_repair_error():
    accessor = _FakeAccessor(
        SemanticQueryResponse.from_error(
            "COLUMN_FIELD_NOT_FOUND: column 'notARealField' is not a query model field"
        )
    )
    client = _client(accessor=accessor)

    response = client.post(
        "/api/v1/query/FactOrderQueryModel/validate",
        json={"limit": 3, "columns": ["orderId", "notARealField"]},
    )

    body = response.json()
    assert body["success"] is False
    assert body["runtimeApiVersion"] == "foggy-runtime-api/v1"
    assert body["error"]["code"] == "FIELD_NOT_FOUND"
    assert body["error"]["phase"] == "query.validate"
    assert body["error"]["model"] == "FactOrderQueryModel"
    assert body["error"]["field"] == "notARealField"
    assert body["error"]["safeToAutoRepair"] is True


def test_models_validate_loads_path_without_mutating_service(monkeypatch, tmp_path):
    from foggy.dataset_model.impl import loader

    calls = []

    def fake_load(path, namespace=None):
        calls.append({"path": path, "namespace": namespace})
        return [SimpleNamespace(name="FactOrderQueryModel")]

    monkeypatch.setattr(loader, "load_models_from_directory", fake_load)
    client = _client()

    response = client.post(
        "/api/v1/models/validate",
        json={"path": str(tmp_path), "namespace": "default"},
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["namespace"] == "default"
    assert body["data"]["modelCount"] == 1
    assert body["data"]["models"] == ["FactOrderQueryModel"]
    assert calls == [{"path": str(tmp_path.resolve()), "namespace": None}]


def test_models_refresh_reloads_configured_sources_and_registers_models(monkeypatch, tmp_path):
    from foggy.dataset_model.impl import loader

    calls = []

    def fake_load(path, namespace=None):
        calls.append({"path": path, "namespace": namespace})
        return [SimpleNamespace(name="FactOrderQueryModel")]

    monkeypatch.setattr(loader, "load_models_from_directory", fake_load)
    service = _FakeSemanticService()
    state = SimpleNamespace(
        semantic_service=service,
        accessor=_FakeAccessor(SemanticQueryResponse(items=[])),
        properties=SimpleNamespace(model_directories=[str(tmp_path)], model_bundles=[]),
    )
    client = _client(state=state)

    response = client.post("/api/v1/models/refresh", json={"namespace": "default"})

    body = response.json()
    assert body["success"] is True
    assert body["data"]["modelCount"] == 1
    assert body["data"]["sources"][0]["namespace"] == "default"
    assert service.registered == ["FactOrderQueryModel"]
    assert service.cache_invalidations == 1
    assert calls == [{"path": str(tmp_path), "namespace": None}]


def test_table_inspect_sqlite_returns_column_metadata():
    executor = _FakeExecutor(rows=[
        {
            "cid": 0,
            "name": "order_id",
            "type": "TEXT",
            "notnull": 0,
            "dflt_value": None,
            "pk": 0,
        },
        {
            "cid": 1,
            "name": "pay_amount",
            "type": "REAL",
            "notnull": 1,
            "dflt_value": None,
            "pk": 0,
        },
    ])
    state = SimpleNamespace(
        semantic_service=_FakeSemanticService(),
        accessor=_FakeAccessor(SemanticQueryResponse(items=[])),
        properties=SimpleNamespace(model_directories=[], model_bundles=[]),
        executor_manager=_FakeExecutorManager(executor),
        data_source_manager=_FakeDataSourceManager(
            SimpleNamespace(source_type="sqlite", schema_name=None)
        ),
    )
    client = _client(state=state)

    response = client.post("/api/v1/tables/inspect", json={"table": "fact_order"})

    body = response.json()
    assert body["success"] is True
    assert body["data"]["sourceType"] == "sqlite"
    assert body["data"]["table"] == "fact_order"
    assert body["data"]["columnCount"] == 2
    assert body["data"]["columns"][0]["name"] == "order_id"
    assert body["data"]["columns"][0]["nullable"] is True
    assert body["data"]["columns"][1]["nullable"] is False
    assert executor.calls[0]["sql"] == 'PRAGMA table_info("fact_order")'


def test_table_inspect_rejects_invalid_identifier():
    client = _client()

    response = client.post("/api/v1/tables/inspect", json={"table": "fact_order;drop"})

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TABLE_INSPECT_FAILED"
    assert body["error"]["phase"] == "tables.inspect"
