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

from foggy.mcp.spi import LocalDatasetAccessor, SemanticMetadataRequest
from foggy.dataset_model.semantic import SemanticQueryService


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

    async def handle_request(request: McpJsonRpcRequest) -> McpJsonRpcResponse:
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
                    models = _get_service().get_all_model_names()
                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": json.dumps({
                                    "models": models,
                                    "count": len(models)
                                }, ensure_ascii=False)
                            }]
                        }
                    )

                elif tool_name in ("get_metadata", "dataset.get_metadata"):
                    # Default: markdown format (aligned with Java LocalDatasetAccessor)
                    # Markdown is ~40-60% fewer tokens and better for LLM comprehension
                    svc = _get_service()
                    fmt = tool_args.get("format", "markdown")

                    if fmt == "json":
                        v3_data = svc.get_metadata_v3()
                        text = json.dumps(v3_data, ensure_ascii=False, indent=2)
                    else:
                        text = svc.get_metadata_v3_markdown()

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
                    model_name = tool_args.get("model")
                    if not model_name:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": "model parameter required"}
                        )

                    meta_request = SemanticMetadataRequest(
                        model=model_name,
                        include_dimensions=True,
                        include_measures=True,
                        include_columns=True,
                    )
                    response = _get_service().get_metadata(meta_request)

                    if not response.models:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32602, "message": f"Model not found: {model_name}"}
                        )

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": json.dumps(response.models[0], ensure_ascii=False, indent=2)
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

                    # V3 format: {model, payload: {columns, slice, groupBy, ...}, mode}
                    # Payload is passed through as-is (Java camelCase field names)
                    payload = tool_args.get("payload", {})
                    mode = tool_args.get("mode", "execute")

                    _acc = _get_accessor()
                    if hasattr(_acc, 'query_model_async'):
                        response = await _acc.query_model_async(model_name, payload, mode=mode)
                    else:
                        response = _acc.query_model(model_name, payload, mode=mode)

                    # Check for internal error
                    if response.error:
                        return McpJsonRpcResponse(
                            id=request.id,
                            error={"code": -32001, "message": response.error}
                        )

                    # Serialize using Pydantic aliases → Java-compatible JSON
                    result_data = _json_serializable(
                        response.model_dump(by_alias=True, exclude_none=True)
                    )

                    return McpJsonRpcResponse(
                        id=request.id,
                        result={
                            "content": [{
                                "type": "text",
                                "text": json.dumps(result_data, ensure_ascii=False, indent=2)
                            }]
                        }
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
            resp = await handle_request(mcp_req)
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
        response = await handle_request(mcp_req)

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