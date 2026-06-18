"""Foggy Runtime API v1 router.

This adapter exposes the Java-first Runtime API contract while keeping the
existing Python semantic service and MCP routes unchanged.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from foggy.mcp_spi import MetadataFormat, SemanticMetadataRequest


RUNTIME_API_VERSION = "foggy-runtime-api/v1"
SCHEMA_VERSION = "2026-06-06"
ENGINE = "python"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _json_serializable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return _json_serializable(asdict(value))
    if isinstance(value, dict):
        return {k: _json_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_serializable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_serializable(value.model_dump(by_alias=True, exclude_none=True))
    return value


def _envelope(
    *,
    success: bool,
    data: Any = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> JSONResponse:
    payload = {
        "success": success,
        "engine": ENGINE,
        "runtimeApiVersion": RUNTIME_API_VERSION,
        "data": _json_serializable(data),
        "diagnostics": diagnostics or {"warnings": []},
        "error": error,
    }
    return JSONResponse(content=_json_serializable(payload), status_code=status_code)


def _unsupported(capability: str, phase: str) -> JSONResponse:
    return _envelope(
        success=False,
        data=None,
        error={
            "code": "CAPABILITY_UNSUPPORTED",
            "phase": phase,
            "capability": capability,
            "safeToAutoRepair": False,
        },
    )


def _effective_namespace(value: Any) -> Optional[str]:
    if value is None:
        return None
    namespace = str(value).strip()
    if not namespace or namespace == "default":
        return None
    return namespace


def _runtime_namespace(value: Any) -> str:
    namespace = _effective_namespace(value)
    return namespace or "default"


def _resolve_model_path(raw_path: Any) -> Optional[str]:
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path.resolve())


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(IDENTIFIER_RE.fullmatch(value))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _source_type_value(config: Any, executor: Any) -> str:
    source_type = getattr(config, "source_type", None)
    if source_type is not None:
        return str(getattr(source_type, "value", source_type)).lower()
    class_name = executor.__class__.__name__.lower() if executor else ""
    if "sqlite" in class_name:
        return "sqlite"
    if "postgres" in class_name:
        return "postgresql"
    if "mysql" in class_name:
        return "mysql"
    if "sqlserver" in class_name:
        return "sqlserver"
    return "unknown"


def _bool_from_db(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().upper() in {"YES", "Y", "TRUE", "T", "1"}


def _normalize_inspect_columns(rows: list[dict[str, Any]], source_type: str) -> list[dict[str, Any]]:
    columns = []
    for index, row in enumerate(rows, start=1):
        if source_type == "sqlite":
            columns.append({
                "name": row.get("name"),
                "dataType": row.get("type"),
                "nullable": not _bool_from_db(row.get("notnull")),
                "primaryKey": _bool_from_db(row.get("pk")),
                "defaultValue": row.get("dflt_value"),
                "ordinalPosition": row.get("cid", index),
            })
            continue

        key = row.get("columnKey") or row.get("COLUMN_KEY") or row.get("constraintType")
        columns.append({
            "name": row.get("name") or row.get("column_name") or row.get("COLUMN_NAME"),
            "dataType": row.get("dataType") or row.get("data_type") or row.get("DATA_TYPE"),
            "nullable": _bool_from_db(row.get("nullable") or row.get("is_nullable") or row.get("IS_NULLABLE")),
            "primaryKey": str(key or "").upper() in {"PRI", "PRIMARY KEY"},
            "defaultValue": row.get("defaultValue") or row.get("column_default") or row.get("COLUMN_DEFAULT"),
            "ordinalPosition": row.get("ordinalPosition") or row.get("ordinal_position") or row.get("ORDINAL_POSITION") or index,
        })
    return columns


def _extract_first_field(payload: Dict[str, Any]) -> Optional[str]:
    columns = payload.get("columns")
    if isinstance(columns, list) and columns:
        for column in columns:
            if isinstance(column, str) and column:
                return column
    return None


def _extract_error_field(message: str, payload: Dict[str, Any]) -> Optional[str]:
    patterns = [
        r"(?:COLUMN_)?FIELD_NOT_FOUND.*?column\s+['\"]?([A-Za-z0-9_.]+)",
        r"(?:TIMEWINDOW_)?FIELD_NOT_FOUND.*?base\s+field\s+['\"]?([A-Za-z0-9_.]+)",
        r"field\s+not\s+found[:：]\s*['\"]?([A-Za-z0-9_.]+)",
        r"unknown\s+field[:：]\s*['\"]?([A-Za-z0-9_.]+)",
        r"not\s+found[:：]\s*['\"]?([A-Za-z0-9_.]+)",
        r"字段[^A-Za-z0-9_]*([A-Za-z0-9_.]+)[^A-Za-z0-9_]*(?:不存在|未找到)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)

    columns = payload.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, str) and column and column in message:
                return column
    return _extract_first_field(payload)


def _bool_flag(payload: Dict[str, Any], key: str) -> bool:
    value = payload.get(key) if isinstance(payload, dict) else None
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def _script_text(request: Dict[str, Any]) -> str:
    script = request.get("script") if isinstance(request, dict) else None
    return script if isinstance(script, str) else ""


def _request_params(request: Dict[str, Any]) -> Dict[str, Any]:
    params = request.get("params") if isinstance(request, dict) else None
    return dict(params) if isinstance(params, dict) else {}


def _cte_bridge_enabled(request: Dict[str, Any]) -> bool:
    capabilities = request.get("capabilities") if isinstance(request, dict) else None
    options = request.get("options") if isinstance(request, dict) else None
    return _bool_flag(capabilities or {}, "cteBridge") or _bool_flag(options or {}, "cteBridge")


def _compose_error_code(mode: str) -> str:
    if mode == "validate":
        return "COMPOSE_SCRIPT_INVALID"
    if mode == "preview":
        return "COMPOSE_COMPILE_FAILED"
    return "COMPOSE_EXECUTE_FAILED"


def _compose_runtime_code(mode: str) -> str:
    return "COMPOSE_EXECUTE_FAILED" if mode == "execute" else _compose_error_code(mode)


def _compose_phase(mode: str) -> str:
    return f"compose.{mode}"


def _fsscript_error(message: str, *, code: str = "FSSCRIPT_EXECUTE_FAILED") -> Dict[str, Any]:
    return {
        "code": code,
        "phase": "fsscript.execute",
        "message": message,
        "safeToAutoRepair": code != "FSSCRIPT_CTE_BRIDGE_DENIED",
    }


class _RuntimeComposeError(Exception):
    def __init__(
        self,
        *,
        code: str,
        phase: str,
        message: str,
        field: Optional[str] = None,
        safe_to_auto_repair: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.phase = phase
        self.field = field
        self.safe_to_auto_repair = safe_to_auto_repair

    def to_contract_error(self) -> Dict[str, Any]:
        error = {
            "code": self.code,
            "phase": self.phase,
            "message": str(self),
            "safeToAutoRepair": self.safe_to_auto_repair,
        }
        if self.field is not None:
            error["field"] = self.field
        return error


class _FsscriptCteBridgeDenied(Exception):
    pass


def _error_from_query_response(
    *,
    model: str,
    phase: str,
    payload: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    lowered = message.lower()
    if "model not found" in lowered or "unknown model" in lowered:
        return {
            "code": "MODEL_NOT_FOUND",
            "phase": phase,
            "model": model,
            "safeToAutoRepair": True,
            "message": message,
        }

    if (
        "field not found" in lowered
        or "field_not_found" in lowered
        or "unknown field" in lowered
        or "not found" in lowered
        or "不存在" in message
        or "未找到" in message
    ):
        return {
            "code": "FIELD_NOT_FOUND",
            "phase": phase,
            "model": model,
            "field": _extract_error_field(message, payload),
            "safeToAutoRepair": True,
            "message": message,
        }

    return {
        "code": "QUERY_VALIDATE_FAILED" if phase == "query.validate" else "QUERY_EXECUTE_FAILED",
        "phase": phase,
        "model": model,
        "safeToAutoRepair": phase == "query.validate",
        "message": message,
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def create_runtime_api_v1_router(
    *,
    semantic_service: Any = None,
    accessor: Any = None,
    state_getter: Optional[Callable[[], Any]] = None,
) -> APIRouter:
    """Create the Runtime API v1 router for Python parity."""

    router = APIRouter(tags=["runtime-api-v1"])

    def _get_service() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "semantic_service", None) if state else semantic_service
        return semantic_service

    def _get_accessor() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "accessor", None) if state else accessor
        return accessor

    def _get_properties() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "properties", None) if state else None
        return None

    def _get_executor_manager() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "executor_manager", None) if state else None
        return None

    def _get_default_executor() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "executor", None) if state else None
        return None

    def _get_data_source_manager() -> Any:
        if state_getter:
            state = state_getter()
            return getattr(state, "data_source_manager", None) if state else None
        return None

    def _get_authority_resolver() -> Any:
        if state_getter:
            state = state_getter()
            resolver = getattr(state, "authority_resolver", None) if state else None
            if resolver is not None:
                return resolver
        return _AllowAllAuthorityResolver()

    def _get_default_dialect() -> str:
        if state_getter:
            state = state_getter()
            dialect = getattr(state, "default_dialect", None) if state else None
            if dialect:
                return str(dialect)
        return "mysql"

    def _configured_model_sources() -> list[tuple[str, Optional[str]]]:
        properties = _get_properties()
        sources: list[tuple[str, Optional[str]]] = []
        for model_dir in getattr(properties, "model_directories", []) or []:
            if model_dir:
                sources.append((str(model_dir), None))
        for bundle in getattr(properties, "model_bundles", []) or []:
            path = getattr(bundle, "path", None)
            if path:
                sources.append((str(path), _effective_namespace(getattr(bundle, "namespace", None))))
        return sources

    def _register_loaded_models(svc: Any, loaded_models: list[Any], namespace: Optional[str]) -> None:
        for model in loaded_models:
            svc.register_model(model, namespace=namespace)
        if hasattr(svc, "invalidate_model_cache"):
            svc.invalidate_model_cache()

    def _load_models(path: str, namespace: Optional[str]) -> list[Any]:
        from foggy.dataset_model.impl.loader import load_models_from_directory

        return load_models_from_directory(path, namespace=namespace)

    class _AllowAllAuthorityResolver:
        def resolve(self, request: Any) -> Any:
            from foggy.dataset_model.engine.compose.security import (
                AuthorityResolution,
                ModelBinding,
            )

            return AuthorityResolution(bindings={
                model_request.model: ModelBinding(
                    field_access=None,
                    denied_columns=[],
                    system_slice=[],
                )
                for model_request in request.models
            })

    def _build_compose_context(request: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Any:
        from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal

        return ComposeQueryContext(
            principal=Principal(user_id="runtime-api"),
            namespace=_runtime_namespace(request.get("namespace")),
            authority_resolver=_get_authority_resolver(),
            trace_id=request.get("traceId"),
            params=params if params is not None else _request_params(request),
        )

    def _compose_response(result: Any, mode: str, value: Any = None) -> Dict[str, Any]:
        actual_value = result.value if value is None else value
        return {
            "valid": True,
            "scriptKind": "compose",
            "mode": mode,
            "value": actual_value,
            "sql": result.sql,
            "params": list(result.params or []),
            "warnings": list(result.warnings or []),
        }

    def _map_compose_exception(mode: str, exc: Exception) -> _RuntimeComposeError:
        from foggy.dataset_model.engine.compose.compilation.errors import ComposeCompileError
        from foggy.dataset_model.engine.compose.sandbox.exceptions import (
            ComposeSandboxViolationError,
        )
        from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError

        phase = _compose_phase(mode)
        if isinstance(exc, ComposeSandboxViolationError):
            return _RuntimeComposeError(
                code="COMPOSE_SANDBOX_VIOLATION",
                phase=phase,
                message=str(exc),
                safe_to_auto_repair=False,
            )
        if isinstance(exc, ComposeSchemaError):
            return _RuntimeComposeError(
                code=_compose_error_code(mode),
                phase=phase,
                message=str(exc),
                field=getattr(exc, "offending_field", None),
                safe_to_auto_repair=True,
            )
        if isinstance(exc, ComposeCompileError):
            return _RuntimeComposeError(
                code=_compose_error_code(mode),
                phase=phase,
                message=str(exc),
                safe_to_auto_repair=True,
            )
        return _RuntimeComposeError(
            code=_compose_runtime_code(mode),
            phase=phase,
            message=str(exc),
            safe_to_auto_repair=False,
        )

    def _run_compose(request: Dict[str, Any], mode: str) -> Dict[str, Any]:
        from foggy.dataset_model.engine.compose.runtime import run_script
        from foggy.dataset_model.engine.compose.runtime.script_runtime import (
            ScriptResult,
            _run_script_no_intercept,
        )

        script = _script_text(request)
        if not script.strip():
            raise _RuntimeComposeError(
                code="COMPOSE_SCRIPT_INVALID",
                phase=_compose_phase(mode),
                message="parameter 'script' is required and must be non-blank",
                safe_to_auto_repair=True,
            )

        ctx = _build_compose_context(request)
        try:
            if mode == "validate":
                _run_script_no_intercept(
                    script,
                    ctx,
                    semantic_service=_get_service(),
                    dialect=_get_default_dialect(),
                )
                return _compose_response(ScriptResult(value=None), mode, value=None)
            result = run_script(
                script,
                ctx,
                semantic_service=_get_service(),
                dialect=_get_default_dialect(),
                preview_mode=mode == "preview",
            )
            return _compose_response(result, mode)
        except _RuntimeComposeError:
            raise
        except Exception as exc:  # noqa: BLE001 - Runtime API must return envelopes.
            raise _map_compose_exception(mode, exc) from exc

    class _DeniedCteBridge:
        def validate(self, _request: Any = None) -> Any:
            raise _FsscriptCteBridgeDenied("foggy.cte.validate is disabled for this request.")

        def preview(self, _request: Any = None) -> Any:
            raise _FsscriptCteBridgeDenied("foggy.cte.preview is disabled for this request.")

        def execute(self, _request: Any = None) -> Any:
            raise _FsscriptCteBridgeDenied("foggy.cte.execute is disabled for this request.")

    class _CteBridge:
        def __init__(self, parent_request: Dict[str, Any]) -> None:
            self._parent_request = parent_request

        def validate(self, request: Any = None) -> Any:
            return self._invoke("validate", request)

        def preview(self, request: Any = None) -> Any:
            return self._invoke("preview", request)

        def execute(self, request: Any = None) -> Any:
            return self._invoke("execute", request)

        def _invoke(self, mode: str, request: Any = None) -> Any:
            compose_request = self._compose_request(request, mode)
            return _run_compose(compose_request, mode)

        def _compose_request(self, request: Any = None, mode: str = "validate") -> Dict[str, Any]:
            if request is None:
                return {"script": "", "namespace": self._parent_request.get("namespace")}
            if isinstance(request, str):
                return {
                    "script": request,
                    "namespace": self._parent_request.get("namespace"),
                    "params": {},
                }
            if isinstance(request, dict):
                return {
                    "script": request.get("script"),
                    "namespace": request.get("namespace", self._parent_request.get("namespace")),
                    "params": request.get("params", {}),
                    "traceId": request.get("traceId", self._parent_request.get("traceId")),
                }
            raise _RuntimeComposeError(
                code="COMPOSE_SCRIPT_INVALID",
                phase=_compose_phase(mode),
                message="cte request must be a string script or object containing script",
                safe_to_auto_repair=True,
            )

    def _run_fsscript(request: Dict[str, Any]) -> Dict[str, Any]:
        from foggy.fsscript.evaluator import ExpressionEvaluator
        from foggy.fsscript.expressions.control_flow import ReturnException
        from foggy.fsscript.parser import FsscriptParser

        script = _script_text(request)
        if not script.strip():
            raise RuntimeError("parameter 'script' is required and must be non-blank")

        params = _request_params(request)
        cte_bridge = _CteBridge(request) if _cte_bridge_enabled(request) else _DeniedCteBridge()
        context: Dict[str, Any] = {
            "params": dict(params),
            "foggy": {"cte": cte_bridge},
        }
        context.update(params)
        parser = FsscriptParser(script)
        program = parser.parse_program()
        evaluator = ExpressionEvaluator(context=context, module_loader=None, bean_registry=None)
        try:
            value = evaluator.evaluate(program)
        except ReturnException as exc:
            value = getattr(exc, "value", None)
        return {
            "valid": True,
            "scriptKind": "fsscript",
            "mode": "execute",
            "value": value,
            "warnings": [],
        }

    @router.get("/capabilities")
    async def capabilities() -> JSONResponse:
        data = {
            "engine": ENGINE,
            "runtimeApiVersion": RUNTIME_API_VERSION,
            "schemaVersion": SCHEMA_VERSION,
            "enabled": True,
            "securityMode": "none-dev-test-only",
            "capabilities": {
                "runtime.capabilities": "supported",
                "models.list": "supported",
                "models.describe": "supported",
                "models.validate": "supported",
                "models.refresh": "supported",
                "query.validate": "supported",
                "query.execute": "supported",
                "tables.inspect": "supported",
                "compose.validate": "supported",
                "compose.preview": "supported",
                "compose.execute": "supported",
                "fsscript.execute": "supported",
                "fsscript.cteBridge": "supported",
            },
        }
        return _envelope(success=True, data=data)

    @router.get("/models")
    async def list_models() -> JSONResponse:
        svc = _get_service()
        if not svc:
            return _envelope(
                success=False,
                error={
                    "code": "SERVICE_NOT_INITIALIZED",
                    "phase": "models.list",
                    "safeToAutoRepair": False,
                },
            )

        models = svc.get_all_model_names() if hasattr(svc, "get_all_model_names") else []
        return _envelope(success=True, data={"models": models, "count": len(models)})

    @router.post("/models/{model}/describe")
    async def describe_model(
        model: str,
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        svc = _get_service()
        if not svc:
            return _envelope(
                success=False,
                error={
                    "code": "SERVICE_NOT_INITIALIZED",
                    "phase": "models.describe",
                    "model": model,
                    "safeToAutoRepair": False,
                },
            )

        fmt = str(request.get("format") or MetadataFormat.JSON.value).lower()
        try:
            if hasattr(svc, "get_metadata_v3") and fmt == MetadataFormat.JSON.value:
                data = svc.get_metadata_v3(model_names=[model])
                content = json.dumps(data, ensure_ascii=False)
                return _envelope(success=True, data={"format": fmt, "content": content, "data": data})
            if hasattr(svc, "get_metadata_v3_markdown"):
                content = svc.get_metadata_v3_markdown(model_names=[model])
                data = None
                if hasattr(svc, "get_metadata_v3"):
                    data = svc.get_metadata_v3(model_names=[model])
                return _envelope(success=True, data={"format": MetadataFormat.MARKDOWN.value, "content": content, "data": data})

            response = svc.get_metadata(SemanticMetadataRequest(model=model), fmt)
            if getattr(response, "error", None):
                return _envelope(
                    success=False,
                    error={
                        "code": "MODEL_DESCRIBE_FAILED",
                        "phase": "models.describe",
                        "model": model,
                        "safeToAutoRepair": False,
                        "message": response.error,
                    },
                )
            return _envelope(success=True, data=response)
        except Exception as exc:  # noqa: BLE001 - adapter must always return runtime envelope.
            return _envelope(
                success=False,
                error={
                    "code": "MODEL_DESCRIBE_FAILED",
                    "phase": "models.describe",
                    "model": model,
                    "safeToAutoRepair": False,
                    "message": str(exc),
                },
            )

    async def _query(model: str, payload: Dict[str, Any], mode: str) -> JSONResponse:
        acc = _get_accessor()
        phase = f"query.{mode}"
        if not acc:
            return _envelope(
                success=False,
                error={
                    "code": "SERVICE_NOT_INITIALIZED",
                    "phase": phase,
                    "model": model,
                    "safeToAutoRepair": False,
                },
            )

        try:
            if hasattr(acc, "query_model_async"):
                response = await _maybe_await(acc.query_model_async(model, payload, mode=mode))
            else:
                response = await _maybe_await(acc.query_model(model, payload, mode=mode))
        except Exception as exc:  # noqa: BLE001 - convert engine exceptions to contract errors.
            error = _error_from_query_response(
                model=model,
                phase=phase,
                payload=payload,
                message=str(exc),
            )
            return _envelope(success=False, error=error)

        warnings = getattr(response, "warnings", None) or []
        diagnostics = {"warnings": warnings}
        if getattr(response, "sql", None):
            diagnostics["sql"] = response.sql

        message = getattr(response, "error", None)
        if message:
            error = _error_from_query_response(
                model=model,
                phase=phase,
                payload=payload,
                message=message,
            )
            return _envelope(success=False, diagnostics=diagnostics, error=error)

        data = response.model_dump(by_alias=True, exclude_none=True) if hasattr(response, "model_dump") else response
        return _envelope(success=True, data=data, diagnostics=diagnostics)

    @router.post("/query/{model}/validate")
    async def validate_query(
        model: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        return await _query(model, payload, "validate")

    @router.post("/query/{model}/execute")
    async def execute_query(
        model: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        return await _query(model, payload, "execute")

    @router.post("/models/validate")
    async def validate_models(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        path = _resolve_model_path(request.get("path"))
        namespace = _effective_namespace(request.get("namespace"))
        if not path:
            return _envelope(
                success=False,
                error={
                    "code": "MODEL_VALIDATE_FAILED",
                    "phase": "models.validate",
                    "safeToAutoRepair": False,
                    "message": "Missing required field: path",
                },
            )

        try:
            loaded = _load_models(path, namespace)
        except Exception as exc:  # noqa: BLE001 - contract endpoint must envelope failures.
            error = {
                "code": "MODEL_VALIDATE_FAILED",
                "phase": "models.validate",
                "path": path,
                "namespace": namespace or "default",
                "safeToAutoRepair": False,
                "message": str(exc),
            }
            if request.get("includeStackTrace"):
                error["stackTrace"] = repr(exc)
            return _envelope(success=False, error=error)

        if not loaded:
            return _envelope(
                success=False,
                error={
                    "code": "MODEL_VALIDATE_FAILED",
                    "phase": "models.validate",
                    "path": path,
                    "namespace": namespace or "default",
                    "safeToAutoRepair": False,
                    "message": "No models loaded from path",
                },
            )

        return _envelope(
            success=True,
            data={
                "path": path,
                "namespace": namespace or "default",
                "modelCount": len(loaded),
                "models": [getattr(model, "name", None) for model in loaded],
            },
        )

    @router.post("/models/refresh")
    async def refresh_models(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        svc = _get_service()
        if not svc:
            return _envelope(
                success=False,
                error={
                    "code": "SERVICE_NOT_INITIALIZED",
                    "phase": "models.refresh",
                    "safeToAutoRepair": False,
                },
            )

        sources = []
        request_path = _resolve_model_path(request.get("path"))
        request_namespace = _effective_namespace(request.get("namespace"))
        if request_path:
            sources.append((request_path, request_namespace))
        else:
            sources.extend(_configured_model_sources())

        if not sources:
            return _envelope(
                success=False,
                error={
                    "code": "MODEL_REFRESH_FAILED",
                    "phase": "models.refresh",
                    "safeToAutoRepair": False,
                    "message": "No model directories configured",
                },
            )

        clear_existing = bool(request.get("clearExisting", True))
        if clear_existing and request_namespace and hasattr(svc, "unregister_by_namespace"):
            svc.unregister_by_namespace(request_namespace)

        requested_models = [
            str(model).strip()
            for model in request.get("models", []) or []
            if str(model).strip()
        ]
        loaded_summary = []
        loaded_names = []
        loaded_total = 0
        try:
            for path, namespace in sources:
                loaded = _load_models(path, namespace)
                _register_loaded_models(svc, loaded, namespace)
                source_names = [getattr(model, "name", None) for model in loaded]
                loaded_names.extend(name for name in source_names if name)
                loaded_total += len(loaded)
                loaded_summary.append({
                    "path": path,
                    "namespace": namespace or "default",
                    "modelCount": len(loaded),
                    "models": source_names,
                })
        except Exception as exc:  # noqa: BLE001 - contract endpoint must envelope failures.
            error = {
                "code": "MODEL_REFRESH_FAILED",
                "phase": "models.refresh",
                "namespace": request_namespace or "default",
                "safeToAutoRepair": False,
                "message": str(exc),
            }
            if request.get("includeStackTrace"):
                error["stackTrace"] = repr(exc)
            return _envelope(success=False, error=error)

        scope = "models" if requested_models else "namespace"
        refreshed_models = list(dict.fromkeys(requested_models or loaded_names))
        failures = []
        if requested_models:
            loaded_name_set = set(loaded_names)
            failures = [
                {"model": model, "message": f"QM model was not refreshed: {model}"}
                for model in requested_models
                if model not in loaded_name_set
            ]
            refreshed_models = [model for model in requested_models if model in loaded_name_set]

        refresh_data = {
            "namespace": request_namespace or "default",
            "scope": scope,
            "clearedCaches": ["model-catalog"],
            "refreshedModels": refreshed_models,
            "loadedCount": len(refreshed_models),
            "failedCount": len(failures),
            "failures": failures,
            "warnings": [],
        }

        if failures:
            return _envelope(
                success=False,
                diagnostics={"warnings": [], "attributes": {"refresh": refresh_data, "sources": loaded_summary}},
                error={
                    "code": "MODEL_REFRESH_FAILED",
                    "phase": "models.refresh",
                    "model": failures[0]["model"],
                    "safeToAutoRepair": False,
                    "message": failures[0]["message"],
                },
            )

        return _envelope(
            success=True,
            data=refresh_data,
            diagnostics={"warnings": [], "attributes": {"sources": loaded_summary, "modelCount": loaded_total}},
        )

    @router.post("/tables/inspect")
    async def inspect_table(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        table = request.get("table") or request.get("tableName")
        schema = request.get("schema")
        data_source = request.get("dataSource") or request.get("data_source")
        data_source_name = str(data_source) if data_source else None

        if not _valid_identifier(table):
            return _envelope(
                success=False,
                error={
                    "code": "TABLE_INSPECT_FAILED",
                    "phase": "tables.inspect",
                    "safeToAutoRepair": False,
                    "message": "Invalid or missing table identifier",
                },
            )
        if schema is not None and schema != "" and not _valid_identifier(schema):
            return _envelope(
                success=False,
                error={
                    "code": "TABLE_INSPECT_FAILED",
                    "phase": "tables.inspect",
                    "table": table,
                    "safeToAutoRepair": False,
                    "message": "Invalid schema identifier",
                },
            )

        executor_manager = _get_executor_manager()
        executor = executor_manager.get(data_source_name) if executor_manager else _get_default_executor()
        if not executor:
            return _envelope(
                success=False,
                error={
                    "code": "DATA_SOURCE_NOT_FOUND",
                    "phase": "tables.inspect",
                    "dataSource": data_source_name,
                    "safeToAutoRepair": False,
                },
            )

        data_source_manager = _get_data_source_manager()
        data_source_config = data_source_manager.get(data_source_name) if data_source_manager else None
        source_type = _source_type_value(data_source_config, executor)
        schema_name = str(schema) if schema else getattr(data_source_config, "schema_name", None)

        if source_type == "sqlite":
            sql = f"PRAGMA table_info({_quote_identifier(str(table))})"
            params = None
            effective_schema = None
        elif source_type == "mysql":
            effective_schema = schema_name or getattr(data_source_config, "database", None)
            if effective_schema:
                sql = (
                    "SELECT COLUMN_NAME AS name, DATA_TYPE AS dataType, IS_NULLABLE AS nullable, "
                    "COLUMN_DEFAULT AS defaultValue, COLUMN_KEY AS columnKey, ORDINAL_POSITION AS ordinalPosition "
                    "FROM information_schema.columns WHERE table_schema = ? AND table_name = ? "
                    "ORDER BY ORDINAL_POSITION"
                )
                params = [effective_schema, table]
            else:
                sql = (
                    "SELECT COLUMN_NAME AS name, DATA_TYPE AS dataType, IS_NULLABLE AS nullable, "
                    "COLUMN_DEFAULT AS defaultValue, COLUMN_KEY AS columnKey, ORDINAL_POSITION AS ordinalPosition "
                    "FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = ? "
                    "ORDER BY ORDINAL_POSITION"
                )
                params = [table]
        elif source_type == "postgresql":
            effective_schema = schema_name or "public"
            sql = (
                "SELECT column_name AS name, data_type AS dataType, is_nullable AS nullable, "
                "column_default AS defaultValue, ordinal_position AS ordinalPosition "
                "FROM information_schema.columns WHERE table_schema = ? AND table_name = ? "
                "ORDER BY ordinal_position"
            )
            params = [effective_schema, table]
        elif source_type == "sqlserver":
            effective_schema = schema_name or "dbo"
            sql = (
                "SELECT c.COLUMN_NAME AS name, c.DATA_TYPE AS dataType, c.IS_NULLABLE AS nullable, "
                "c.COLUMN_DEFAULT AS defaultValue, c.ORDINAL_POSITION AS ordinalPosition, "
                "tc.CONSTRAINT_TYPE AS constraintType "
                "FROM INFORMATION_SCHEMA.COLUMNS c "
                "LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
                "ON c.TABLE_SCHEMA = kcu.TABLE_SCHEMA AND c.TABLE_NAME = kcu.TABLE_NAME AND c.COLUMN_NAME = kcu.COLUMN_NAME "
                "LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "ON kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
                "WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ? "
                "ORDER BY c.ORDINAL_POSITION"
            )
            params = [effective_schema, table]
        else:
            return _envelope(
                success=False,
                error={
                    "code": "TABLE_INSPECT_FAILED",
                    "phase": "tables.inspect",
                    "dataSource": data_source_name,
                    "safeToAutoRepair": False,
                    "message": f"Unsupported data source type: {source_type}",
                },
            )

        result = await executor.execute(sql, params)
        if getattr(result, "error", None):
            return _envelope(
                success=False,
                diagnostics={"warnings": [], "sql": getattr(result, "sql", sql)},
                error={
                    "code": "TABLE_INSPECT_FAILED",
                    "phase": "tables.inspect",
                    "dataSource": data_source_name,
                    "table": table,
                    "schema": effective_schema,
                    "safeToAutoRepair": False,
                    "message": result.error,
                },
            )

        rows = list(getattr(result, "rows", []) or [])
        if not rows:
            return _envelope(
                success=False,
                diagnostics={"warnings": [], "sql": getattr(result, "sql", sql)},
                error={
                    "code": "TABLE_NOT_FOUND",
                    "phase": "tables.inspect",
                    "dataSource": data_source_name,
                    "table": table,
                    "schema": effective_schema,
                    "safeToAutoRepair": True,
                },
            )

        columns = _normalize_inspect_columns(rows, source_type)
        return _envelope(
            success=True,
            diagnostics={"warnings": [], "sql": getattr(result, "sql", sql)},
            data={
                "dataSource": data_source_name or "default",
                "sourceType": source_type,
                "schema": effective_schema,
                "table": table,
                "columnCount": len(columns),
                "columns": columns,
            },
        )

    @router.post("/compose/validate")
    async def validate_compose(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        try:
            return _envelope(success=True, data=_run_compose(request, "validate"))
        except _RuntimeComposeError as exc:
            return _envelope(success=False, error=exc.to_contract_error())

    @router.post("/compose/preview")
    async def preview_compose(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        try:
            return _envelope(success=True, data=_run_compose(request, "preview"))
        except _RuntimeComposeError as exc:
            return _envelope(success=False, error=exc.to_contract_error())

    @router.post("/compose/execute")
    async def execute_compose(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        try:
            return _envelope(success=True, data=_run_compose(request, "execute"))
        except _RuntimeComposeError as exc:
            return _envelope(success=False, error=exc.to_contract_error())

    @router.post("/fsscript/execute")
    async def execute_fsscript(
        request: Dict[str, Any] = Body(default_factory=dict),
    ) -> JSONResponse:
        try:
            return _envelope(success=True, data=_run_fsscript(request))
        except _FsscriptCteBridgeDenied as exc:
            return _envelope(
                success=False,
                error=_fsscript_error(str(exc), code="FSSCRIPT_CTE_BRIDGE_DENIED"),
            )
        except _RuntimeComposeError as exc:
            return _envelope(success=False, error=exc.to_contract_error())
        except Exception as exc:  # noqa: BLE001 - Runtime API must return envelopes.
            return _envelope(success=False, error=_fsscript_error(str(exc)))

    return router
