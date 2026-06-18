from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from foggy.dataset_model.engine.compose import ComposedSql
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

    def execute_sql(self, sql, params, *, route_model=None):
        return [{"orderId": "FO-001", "routeModel": route_model}]


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


def _patch_compose_compile(monkeypatch):
    captured = []

    def fake_compile(plan, ctx, *, semantic_service, bindings=None,
                     model_info_provider=None, dialect="mysql"):
        captured.append(plan)
        return ComposedSql(sql="SELECT order_id FROM fact_order", params=[])

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.compilation.compiler.compile_plan_to_sql",
        fake_compile,
    )
    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution.compile_plan_to_sql",
        fake_compile,
    )
    return captured


def test_capabilities_returns_runtime_envelope_and_supported_p14_states():
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
    assert body["data"]["capabilities"]["compose.validate"] == "supported"
    assert body["data"]["capabilities"]["compose.preview"] == "supported"
    assert body["data"]["capabilities"]["compose.execute"] == "supported"
    assert body["data"]["capabilities"]["fsscript.execute"] == "supported"
    assert body["data"]["capabilities"]["fsscript.cteBridge"] == "supported"


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
    assert body["data"]["scope"] == "namespace"
    assert body["data"]["loadedCount"] == 1
    assert body["data"]["failedCount"] == 0
    assert body["data"]["refreshedModels"] == ["FactOrderQueryModel"]
    assert body["diagnostics"]["attributes"]["sources"][0]["namespace"] == "default"
    assert service.registered == ["FactOrderQueryModel"]
    assert service.cache_invalidations == 1
    assert calls == [{"path": str(tmp_path), "namespace": None}]


def test_models_refresh_fails_when_requested_model_is_missing(monkeypatch, tmp_path):
    from foggy.dataset_model.impl import loader

    def fake_load(path, namespace=None):
        return [SimpleNamespace(name="FactOrderQueryModel")]

    monkeypatch.setattr(loader, "load_models_from_directory", fake_load)
    service = _FakeSemanticService()
    state = SimpleNamespace(
        semantic_service=service,
        accessor=_FakeAccessor(SemanticQueryResponse(items=[])),
        properties=SimpleNamespace(model_directories=[str(tmp_path)], model_bundles=[]),
    )
    client = _client(state=state)

    response = client.post(
        "/api/v1/models/refresh",
        json={"namespace": "default", "models": ["MissingQueryModel"]},
    )

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "MODEL_REFRESH_FAILED"
    assert body["error"]["phase"] == "models.refresh"
    assert body["error"]["model"] == "MissingQueryModel"
    assert body["error"]["safeToAutoRepair"] is False
    assert body["diagnostics"]["attributes"]["refresh"]["loadedCount"] == 0
    assert body["diagnostics"]["attributes"]["refresh"]["failedCount"] == 1
    assert body["diagnostics"]["attributes"]["refresh"]["failures"][0]["model"] == "MissingQueryModel"


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


def test_compose_validate_success_uses_runtime_envelope():
    client = _client()

    response = client.post(
        "/api/v1/compose/validate",
        json={
            "script": (
                "const plan = dsl({model: 'FactOrderQueryModel', "
                "columns: ['orderId'], limit: 3}); return { plans: plan };"
            )
        },
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["valid"] is True
    assert body["data"]["scriptKind"] == "compose"
    assert body["data"]["mode"] == "validate"


def test_compose_preview_returns_sql_evidence(monkeypatch):
    _patch_compose_compile(monkeypatch)
    client = _client()

    response = client.post(
        "/api/v1/compose/preview",
        json={
            "script": (
                "const plan = dsl({model: 'FactOrderQueryModel', "
                "columns: ['orderId'], limit: 3}); return { plans: plan };"
            )
        },
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["scriptKind"] == "compose"
    assert body["data"]["mode"] == "preview"
    assert body["data"]["value"]["plans"]["sql"] == "SELECT order_id FROM fact_order"


def test_compose_execute_returns_rows(monkeypatch):
    _patch_compose_compile(monkeypatch)
    client = _client()

    response = client.post(
        "/api/v1/compose/execute",
        json={
            "script": (
                "const plan = dsl({model: 'FactOrderQueryModel', "
                "columns: ['orderId'], limit: 3}); return { plans: plan };"
            )
        },
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["mode"] == "execute"
    assert body["data"]["value"]["plans"][0]["orderId"] == "FO-001"


def test_compose_sandbox_violation_maps_contract_error():
    client = _client()

    response = client.post(
        "/api/v1/compose/validate",
        json={"script": "import java.lang.System; return { plans: [] };"},
    )

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "COMPOSE_SANDBOX_VIOLATION"
    assert body["error"]["phase"] == "compose.validate"
    assert body["error"]["safeToAutoRepair"] is False


def test_fsscript_execute_success():
    client = _client()

    response = client.post("/api/v1/fsscript/execute", json={"script": "return 1 + 2;"})

    body = response.json()
    assert body["success"] is True
    assert body["data"]["scriptKind"] == "fsscript"
    assert body["data"]["mode"] == "execute"
    assert body["data"]["value"] == 3


def test_fsscript_cte_bridge_denied_by_default():
    client = _client()

    response = client.post(
        "/api/v1/fsscript/execute",
        json={"script": "return foggy.cte.preview({script: \"return { plans: [] };\"});"},
    )

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FSSCRIPT_CTE_BRIDGE_DENIED"
    assert body["error"]["phase"] == "fsscript.execute"
    assert body["error"]["safeToAutoRepair"] is False


def test_fsscript_cte_bridge_preview_success(monkeypatch):
    _patch_compose_compile(monkeypatch)
    client = _client()

    response = client.post(
        "/api/v1/fsscript/execute",
        json={
            "script": (
                "return foggy.cte.preview({script: \"const plan = dsl({model: "
                "'FactOrderQueryModel', columns: ['orderId'], limit: 3}); "
                "return { plans: plan };\"});"
            ),
            "capabilities": {"cteBridge": True},
        },
    )

    body = response.json()
    assert body["success"] is True
    assert body["data"]["scriptKind"] == "fsscript"
    assert body["data"]["value"]["scriptKind"] == "compose"
    assert body["data"]["value"]["mode"] == "preview"
    assert body["data"]["value"]["value"]["plans"]["sql"] == "SELECT order_id FROM fact_order"
