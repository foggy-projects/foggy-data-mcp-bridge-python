"""MCP RPC Router - Model Context Protocol JSON-RPC endpoint.

This implements the MCP protocol for AI assistants to interact with
the semantic layer.

Protocol: https://modelcontextprotocol.io/
Transport: Streamable HTTP (MCP 2024-11-05)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, Response as FastAPIResponse
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import Response
from pydantic import BaseModel, Field
import logging
import json
import asyncio
import uuid

from foggy.mcp_spi import LocalDatasetAccessor, SemanticMetadataRequest
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.mcp_spi.semantic import DeniedColumn
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp.tools.compose_script_tool import ComposeScriptTool


logger = logging.getLogger(__name__)


def _json_serializable(obj):
    """Convert obj to JSON-serializable form (handle Decimal, datetime, etc.)."""
    import decimal
    from datetime import datetime, date
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_serializable(i) for i in obj]
    return obj


# Session storage for SSE connections
_sse_sessions: Dict[str, asyncio.Queue] = {}


# MCP Protocol Models
class McpJsonRpcRequest(BaseModel):
    """MCP JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    id: Optional[str | int] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class McpJsonRpcResponse(BaseModel):
    """MCP JSON-RPC 2.0 Response.

    Per JSON-RPC 2.0 spec: response MUST have either 'result' or 'error',
    never both. Use model_dump(exclude_none=True) for serialization.
    """
    jsonrpc: str = "2.0"
    id: Optional[str | int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_json_rpc(self) -> dict:
        """Serialize per JSON-RPC 2.0: exclude null result/error."""
        d: dict = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result if self.result is not None else {}
        return d


class McpTool(BaseModel):
    """MCP Tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class McpResource(BaseModel):
    """MCP Resource definition."""
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: str = "application/json"


# Tool Definitions — loaded from shared schema files (same as Java project)
from foggy.mcp.schemas.tool_config_loader import get_tool_config_loader

def _load_tools():
    """Load tool definitions from shared schema files.

    Source of truth: foggy-data-mcp-bridge/foggy-dataset-mcp/src/main/resources/schemas/
    When adding/modifying tools, update the schema files, not this code.
    """
    loader = get_tool_config_loader()
    tools_from_files = {t.name: t for t in loader.get_tools()}

    # Convert to McpTool instances
    result = []
    for name, tool_def in tools_from_files.items():
        result.append(McpTool(
            name=tool_def.name,
            description=tool_def.description,
            inputSchema=tool_def.inputSchema,
        ))
    return result

SHARED_TOOLS = _load_tools()


def _build_text_content(text: str) -> list[dict[str, str]]:
    return [{
        "type": "text",
        "text": text,
    }]


def _header_value(headers: Dict[str, str], name: str) -> Optional[str]:
    value = headers.get(name)
    if value is not None:
        return value
    lowered = name.lower()
    for key, candidate in headers.items():
        if key.lower() == lowered:
            return candidate
    return None


def _missing_compose_authority_resolver(_context):
    raise RuntimeError(
        "dataset.compose_script requires host-provided authority binding or embedded authority resolver"
    )


def _normalize_denied_columns(raw_denied_columns: Any) -> Optional[list[dict[str, Any]]]:
    """Normalize deniedColumns from Odoo grouped form to flat engine form.

    Odoo v1.3 sends grouped entries like:
        [{"table": "hr_employee", "columns": ["gender", "marital"]}]

    Python semantic service expects flat entries like:
        [{"table": "hr_employee", "column": "gender"}, ...]
    """
    if not isinstance(raw_denied_columns, list):
        return None

    normalized: list[dict[str, Any]] = []
    for item in raw_denied_columns:
        if not isinstance(item, dict):
            continue

        table = item.get("table")
        schema = item.get("schema")
        column = item.get("column")
        if table and column:
            entry = {"table": table, "column": column}
            if schema:
                entry["schema"] = schema
            normalized.append(entry)
            continue

        columns = item.get("columns")
        if not table or not isinstance(columns, list):
            continue
        for col in columns:
            if not col:
                continue
            entry = {"table": table, "column": col}
            if schema:
                entry["schema"] = schema
            normalized.append(entry)

    return normalized


def _build_denied_column_models(raw_denied_columns: Any) -> Optional[list[DeniedColumn]]:
    normalized = _normalize_denied_columns(raw_denied_columns)
    if normalized is None:
        return None
    return [DeniedColumn(**item) for item in normalized]


def _normalize_query_error_text(error_text: str) -> str:
    """Normalize engine business failures to the Odoo-facing wording contract."""
    if not error_text:
        return error_text

    stripped = error_text.strip()
    lowered = stripped.lower()
    if stripped.startswith("查询被拒绝") or stripped.startswith("查询执行失败"):
        return stripped
    if "column governance" in lowered or "not accessible" in lowered:
        return f"查询被拒绝：{stripped}"
    return stripped


def create_mcp_router(
    semantic_service: SemanticQueryService = None,
    accessor: LocalDatasetAccessor = None,
    state_getter=None,
) -> APIRouter:
    """Create MCP RPC router.

    Args:
        semantic_service: Semantic query service (can be None if state_getter provided)
        accessor: Dataset accessor (can be None if state_getter provided)
        state_getter: Callable that returns AppState for lazy resolution

    Returns:
        FastAPI router with MCP endpoints
    """
    router = APIRouter(tags=["mcp"])

    def _get_service():
        if state_getter:
            s = state_getter()
            return s.semantic_service if s else semantic_service
        return semantic_service

    def _get_accessor():
        if state_getter:
            s = state_getter()
            return s.accessor if s else accessor
        return accessor

    # Available tools — loaded from shared schema files (aligned with Java)
    TOOLS = SHARED_TOOLS

    async def handle_request(
        request: McpJsonRpcRequest,
        http_headers: Optional[Dict[str, str]] = None,
    ) -> McpJsonRpcResponse:
        """Handle MCP JSON-RPC request."""
        try:
            method = request.method
            params = request.params or {}

            # Initialize
            if method == "initialize":
                return McpJsonRpcResponse(
                    id=request.id,
                    result={
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                        },
                        "serverInfo": {
                            "name": "foggy-mcp-server",
                            "version": "1.0.0"
                        }
                    }
                )

            # List tools
            elif method == "tools/list":
                return McpJsonRpcResponse(
                    id=request.id,
                    result={
                        "tools": [t.model_dump() for t in TOOLS]
                    }
                )

            # Call tool
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                if tool_name in ("list_models", "dataset.list_models"):
                    svc = _get_service()
                    models = svc.get_all_model_names()
                    
                    lines = [
                        "### 📚 可用数据模型列表 (Available Models)",
                        "",
                        "**AI 助手请注意**：",
                        "1. 这是当前工作空间中 **全部可用** 的数据模型。请根据用户的业务意图（如“分析销售”、“查看库存”）选择合适的模型。",
                        "2. 选择模型后，请务必使用 `dataset.describe_model_internal` 深入了解该模型的可用字段（Dimensions/Measures）。",
                        "",
                        "| 模型名称 | 别名/说明 | 时间轴角色 | 推荐提示词 |",
                        "|---|---|---|---|",
                    ]
                    
                    for model_name in models:
                        qm = svc.get_model(model_name)
                        if not qm:
                            continue
                            
                        alias = qm.alias or "-"
                        
                        time_role_str = "-"
                        for dim in qm.dimensions.values():
                            if dim.is_time_dimension():
                                time_role_str = "✓ TIME"
                                break
                                
                        lines.append(f"| `{model_name}` | {alias} | {time_role_str} | `使用 {model_name} 查询...` |")
                        
                    lines.append("")
                    lines.append("> 💡 **提示**：如果有多个模型名称相似，请优先参考 `别名/说明` 列来确定最匹配业务意图的模型。")
                    
                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": "\n".join(lines)
                            }]
                        }
                    )

                elif tool_name in ("get_metadata", "dataset.get_metadata"):
                    # AI Chat 契约（v1.3）：
                    #   - LLM 可见 schema 不暴露 `format`（见 schemas/get_metadata_schema.json）。
                    #     LLM 的 tool call 里不会有 format，因此默认走 markdown 分支，
                    #     AI Chat 路径 deterministic。
                    #   - 内部程序化消费方（Odoo Pro 网关模式下的列权限 / 字段映射服务等）
                    #     会显式传 `format='json'` 经过本入口获取结构化 JSON。这里必须继续
                    #     按原分支返回 JSON，否则会破坏 Model Overview / Mapping Preview
                    #     等管理端结构化解析链路（参见总控治理原则）。
                    svc = _get_service()
                    fmt = tool_args.get("format", "markdown")
                    # v1.2 column governance: optional visible_fields filter
                    visible_fields = tool_args.get("visibleFields")
                    # v1.3 physical-column governance
                    denied_columns = _build_denied_column_models(tool_args.get("deniedColumns"))

                    if fmt == "json":
                        v3_data = svc.get_metadata_v3(
                            visible_fields=visible_fields,
                            denied_columns=denied_columns,
                        )
                        text = json.dumps(v3_data, ensure_ascii=False, indent=2)
                    else:
                        text = svc.get_metadata_v3_markdown(
                            visible_fields=visible_fields,
                            denied_columns=denied_columns,
                        )

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": text,
                            }]
                        }
                    )

                elif tool_name in ("describe_model_internal", "dataset.describe_model_internal"):
                    # AI Chat 契约（v1.3）：LLM 不能选择格式（schema 不暴露 format）。
                    # LLM 的 tool call 默认不带 format → 默认 markdown。
                    # 内部程序化消费方（Odoo Pro 列权限 / 字段映射 / 管理端预览等）会显式
                    # 传 format='json'，此处按原分支返回结构化 JSON，不得强行覆盖。
                    model_name = tool_args.get("model")
                    if not model_name:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": "model parameter required"}
                        )

                    svc = _get_service()
                    fmt = tool_args.get("format", "markdown")
                    denied_columns = _build_denied_column_models(tool_args.get("deniedColumns"))

                    if fmt == "json":
                        v3_data = svc.get_metadata_v3(
                            model_names=[model_name],
                            denied_columns=denied_columns,
                        )
                        if model_name not in (v3_data.get("models") or {}):
                            return McpJsonRpcResponse(
                                id=request.id,
                                error={"code": -32602, "message": f"Model not found: {model_name}"}
                            )
                        text = json.dumps(v3_data, ensure_ascii=False, indent=2)
                    else:
                        # V3 markdown format — 比 JSON 少约 40-60% token，
                        # 且 JOIN 维度会展开成 {dim}$id / {dim}$caption。
                        text = svc.get_metadata_v3_markdown(
                            model_names=[model_name],
                            denied_columns=denied_columns,
                        )

                    if text.startswith("# 暂无可用数据模型"):
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": f"Model not found: {model_name}"}
                        )

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": text,
                            }]
                        }
                    )

                elif tool_name in ("query_model", "dataset.query_model"):
                    model_name = tool_args.get("model")
                    if not model_name:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": "model parameter required"}
                        )

                    if "payload" not in tool_args or tool_args.get("payload") is None:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": "payload parameter required"}
                        )

                    # V3 format: {model, payload: {columns, slice, groupBy, ...}, mode}
                    # Payload is passed through as-is (Java camelCase field names)
                    payload = tool_args["payload"]
                    mode = tool_args.get("mode", "execute")
                    normalized_denied_columns = _normalize_denied_columns(
                        tool_args.get("deniedColumns")
                    )
                    if isinstance(payload, dict):
                        if "deniedColumns" not in payload and normalized_denied_columns is not None:
                            payload = dict(payload)
                            payload["deniedColumns"] = normalized_denied_columns
                        if "systemSlice" not in payload and "systemSlice" in tool_args:
                            if payload is tool_args["payload"]:
                                payload = dict(payload)
                            payload["systemSlice"] = tool_args["systemSlice"]

                    _acc = _get_accessor()
                    if hasattr(_acc, 'query_model_async'):
                        response = await _acc.query_model_async(model_name, payload, mode=mode)
                    else:
                        response = _acc.query_model(model_name, payload, mode=mode)

                    # Check for internal error
                    if response.error:
                        return McpJsonRpcResponse(
                            id=request.id,
                            result={
                                "status": "failed",
                                "content": _build_text_content(
                                    _normalize_query_error_text(response.error)
                                ),
                            }
                        )

                    # Serialize using Pydantic aliases → Java-compatible JSON
                    result_data = _json_serializable(
                        response.model_dump(by_alias=True, exclude_none=True)
                    )

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "status": "success",
                            "content": _build_text_content(
                                json.dumps(result_data, ensure_ascii=False, indent=2)
                            ),
                        }
                    )

                elif tool_name == "dataset.compose_script":
                    headers = dict(http_headers or {})
                    tool_context = ToolExecutionContext.create(
                        request_id=str(request.id or uuid.uuid4()),
                        user_id=_header_value(headers, "X-User-Id"),
                        namespace=(
                            _header_value(headers, "X-Namespace")
                            or _header_value(headers, "X-NS")
                        ),
                        headers=headers,
                    )
                    compose_tool = ComposeScriptTool(
                        _missing_compose_authority_resolver,
                        _get_service(),
                        default_dialect="postgresql",
                    )
                    tool_result = await compose_tool.execute(dict(tool_args or {}), context=tool_context)
                    if tool_result.success:
                        payload = {"status": "success"}
                        if isinstance(tool_result.data, dict):
                            payload.update(tool_result.data)
                        else:
                            payload["value"] = tool_result.data
                    else:
                        payload = {
                            "status": "error",
                            "data": tool_result.data or {
                                "error_code": tool_result.error_code,
                                "message": tool_result.error,
                            },
                        }
                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": _build_text_content(
                                json.dumps(_json_serializable(payload), ensure_ascii=False)
                            )
                        },
                    )

                elif tool_name in ("validate_query", "dataset.validate_query"):
                    model_name = tool_args.get("model")
                    if not model_name:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": "model parameter required"}
                        )

                    payload = tool_args.get("payload", {})

                    _acc = _get_accessor()
                    if hasattr(_acc, 'query_model_async'):
                        response = await _acc.query_model_async(model_name, payload, mode="validate")
                    else:
                        response = _acc.query_model(model_name, payload, mode="validate")

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": json.dumps({
                                    "valid": response.error is None,
                                    "sql": response.sql,
                                    "columns": response.columns,
                                    "errors": [response.error] if response.error else [],
                                }, ensure_ascii=False, indent=2)
                            }]
                        }
                    )

                else:
                    return McpJsonRpcResponse(
                        id=request.id,
                        error={"code": -32601, "message": f"Unknown tool: {tool_name}"}
                    )

            # List resources
            elif method == "resources/list":
                models = _get_service().get_all_model_names()
                resources = [
                    McpResource(
                        uri=f"model://{name}",
                        name=name,
                        description=f"Semantic model: {name}"
                    ).model_dump()
                    for name in models
                ]
                return McpJsonRpcResponse(
                    id=request.id,
                    result={"resources": resources}
                )

            # Read resource
            elif method == "resources/read":
                uri = params.get("uri", "")
                if uri.startswith("model://"):
                    model_name = uri[8:]
                    meta_request = SemanticMetadataRequest(model=model_name)
                    response = _get_service().get_metadata(meta_request)
                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "contents": [{
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
                            }]
                        }
                    )
                return McpJsonRpcResponse(
                    id=request.id,
                    error={"code": -32602, "message": f"Unknown resource: {uri}"}
                )

            # List prompts
            elif method == "prompts/list":
                return McpJsonRpcResponse(
                    id=request.id,
                    result={"prompts": []}
                )

            # Ping
            elif method == "ping":
                return McpJsonRpcResponse(
                    id=request.id,
                    result={}
                )

            else:
                return McpJsonRpcResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Method not found: {method}"}
                )

        except Exception as e:
            logger.exception(f"MCP request failed: {e}")
            return McpJsonRpcResponse(
                id=request.id,
                error={"code": -32603, "message": str(e)}
            )

    @router.api_route("/rpc", methods=["GET", "POST", "DELETE"])
    async def mcp_rpc_streamable(request: Request):
        """MCP Streamable HTTP transport at /rpc endpoint.

        Implements MCP 2025-03-26 / 2024-11-05 Streamable HTTP:
        - POST: Handle JSON-RPC request, return JSON or SSE
        - GET: Return SSE stream for server-initiated messages
        - DELETE: Terminate session
        """
        if request.method == "GET":
            return await _handle_sse_stream(request)

        if request.method == "DELETE":
            session_id = request.headers.get("mcp-session-id")
            if session_id and session_id in _sse_sessions:
                del _sse_sessions[session_id]
            return JSONResponse(content={}, status_code=200)

        # POST: handle JSON-RPC
        return await _handle_mcp_post(request, handle_request)

    @router.post("/rpc/batch")
    async def mcp_rpc_batch(requests: List[McpJsonRpcRequest]) -> JSONResponse:
        """MCP JSON-RPC batch endpoint.

        Handles multiple requests in a single call.
        """
        responses = []
        for req in requests:
            resp = await handle_request(req)
            responses.append(resp.to_json_rpc())
        return JSONResponse(content=responses)

    @router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp_streamable_http(request: Request):
        """MCP Streamable HTTP transport at /mcp sub-path."""
        if request.method == "GET":
            return await _handle_sse_stream(request)
        if request.method == "DELETE":
            return JSONResponse(content={}, status_code=200)
        return await _handle_mcp_post(request, handle_request)

    @router.api_route("", methods=["GET", "POST", "DELETE"])
    async def mcp_root(request: Request):
        """MCP endpoint at root path (/mcp/analyst)."""
        if request.method == "GET":
            return await _handle_sse_stream(request)
        if request.method == "DELETE":
            return JSONResponse(content={}, status_code=200)
        return await _handle_mcp_post(request, handle_request)

    return router


async def _handle_mcp_post(request: Request, handle_request):
    """Handle POST request for MCP Streamable HTTP transport.

    Key behaviors:
    - JSON-RPC notifications (no "id" field) return 202 Accepted with no body
    - Requests with "id" return JSON or SSE based on Accept header
    - Mcp-Session-Id header is always set for session tracking
    """
    global _sse_sessions

    accept_header = request.headers.get("accept", "")
    want_sse = "text/event-stream" in accept_header

    # Get or create session ID
    session_id = request.headers.get("mcp-session-id")
    if not session_id:
        session_id = str(uuid.uuid4())

    mcp_headers = {"Mcp-Session-Id": session_id}

    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
            headers=mcp_headers,
        )

    # Handle batch
    if isinstance(body, list):
        responses = []
        has_notifications_only = True
        for req in body:
            if "id" not in req or req.get("id") is None:
                # Notification — no response needed
                continue
            has_notifications_only = False
            mcp_req = McpJsonRpcRequest(**req)
            resp = await handle_request(mcp_req, dict(request.headers))
            responses.append(resp.to_json_rpc())

        if has_notifications_only:
            return Response(status_code=202, headers=mcp_headers)

        if want_sse:
            return _create_sse_response(responses, session_id)
        return JSONResponse(content=responses, headers=mcp_headers)

    else:
        # Single request
        # Check if this is a notification (no "id" field)
        if "id" not in body or body.get("id") is None:
            # Notification (e.g., "notifications/initialized") → 202 Accepted
            logger.debug(f"MCP notification: {body.get('method', '?')}")
            return Response(status_code=202, headers=mcp_headers)

        mcp_req = McpJsonRpcRequest(**body)
        response = await handle_request(mcp_req, dict(request.headers))

        if want_sse:
            return _create_sse_response([response.to_json_rpc()], session_id)

        return JSONResponse(content=response.to_json_rpc(), headers=mcp_headers)


def _create_sse_response(messages: List[dict], session_id: str) -> StreamingResponse:
    """Create an SSE streaming response with JSON-RPC messages."""

    async def event_generator():
        for msg in messages:
            yield f"event: message\ndata: {json.dumps(msg)}\n\n"
        # Send end event
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Mcp-Session-Id": session_id,
        }
    )


async def _handle_sse_stream(request: Request):
    """Handle GET request for SSE stream.

    Returns an SSE stream that can receive server-to-client messages.
    """
    global _sse_sessions

    session_id = request.headers.get("mcp-session-id") or str(uuid.uuid4())

    # Create a queue for this session
    queue = asyncio.Queue()
    _sse_sessions[session_id] = queue

    async def event_generator():
        try:
            # Send endpoint event with session ID
            yield f"event: endpoint\ndata: {json.dumps({'sessionId': session_id})}\n\n"

            while True:
                try:
                    # Wait for messages with timeout
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if msg is None:  # Shutdown signal
                        break
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"event: ping\ndata: {{}}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup session
            if session_id in _sse_sessions:
                del _sse_sessions[session_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Mcp-Session-Id": session_id,
        }
    )
