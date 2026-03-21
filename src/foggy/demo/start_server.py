#!/usr/bin/env python
"""MCP Server startup script with sample data.

This script:
1. Creates an in-memory SQLite database with sample data
2. Registers sample TM models
3. Starts the FastAPI server with MCP RPC endpoint

Usage:
    python -m foggy.demo.start_server [--port 8080] [--host 0.0.0.0]

MCP Endpoint:
    http://localhost:8080/mcp/analyst/rpc
"""

import sys
import asyncio
import argparse
import logging
from typing import Optional

# Setup path for development
sys.path.insert(0, ".")


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


def setup_logging(debug: bool = False):
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


async def create_sample_database():
    """Create sample database with test data."""
    from foggy.dataset.db.executor import SQLiteExecutor

    executor = SQLiteExecutor(":memory:")

    # Create sales table
    await executor.execute("""
        CREATE TABLE sales (
            order_id TEXT PRIMARY KEY,
            sale_date TEXT,
            product_id TEXT,
            product_name TEXT,
            category_name TEXT,
            region_code TEXT,
            region_name TEXT,
            customer_id TEXT,
            customer_segment TEXT,
            quantity INTEGER,
            amount REAL,
            profit REAL
        )
    """)

    # Create inventory table
    await executor.execute("""
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            warehouse_id TEXT,
            inventory_date TEXT,
            quantity INTEGER,
            reorder_flag INTEGER
        )
    """)

    # Generate sample data
    from foggy.demo.models.sample_models import generate_sample_sales_data
    sample_data = generate_sample_sales_data(500, seed=42)

    # Insert sample data
    for record in sample_data:
        await executor.execute(
            """
            INSERT INTO sales (
                order_id, sale_date, product_id, product_name, category_name,
                region_code, region_name, customer_id, customer_segment,
                quantity, amount, profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record["order_id"], record["sale_date"], record["product_id"],
                record["product_name"], record["category_name"], record["region_code"],
                record["region_name"], record["customer_id"], record["customer_segment"],
                record["quantity"], record["amount"], record["profit"]
            ]
        )

    # Insert sample inventory data
    import random
    random.seed(42)
    for i in range(100):
        await executor.execute(
            """
            INSERT INTO inventory (product_id, warehouse_id, inventory_date, quantity, reorder_flag)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                f"PRD-{random.randint(1, 100):03d}",
                f"WH-{random.randint(1, 5)}",
                f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                random.randint(0, 1000),
                1 if random.random() < 0.2 else 0
            ]
        )

    return executor


def create_app_with_sample_data(executor):
    """Create FastAPI app with sample data and models."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    from foggy.dataset_model.semantic import SemanticQueryService
    from foggy.mcp_spi import LocalDatasetAccessor
    from foggy.mcp.routers.mcp_rpc import create_mcp_router
    from foggy.demo.models.sample_models import create_all_sample_models

    # Create semantic service with executor
    service = SemanticQueryService(executor=executor)

    # Register sample models
    models = create_all_sample_models()
    for name, model in models.items():
        service.register_model(model)

    # Create accessor
    accessor = LocalDatasetAccessor(service)

    # Create FastAPI app
    app = FastAPI(
        title="Foggy MCP Demo Server",
        version="1.0.0",
        description="Demo MCP server with sample sales and inventory data",
    )

    # Add CORS with all origins for demo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )

    # Root endpoint - simple info
    @app.get("/")
    async def root():
        return {
            "name": "Foggy MCP Demo Server",
            "version": "1.0.0",
            "models": service.get_all_model_names(),
            "docs": "/docs",
            "mcp_endpoint": "/mcp/analyst",
            "mcp_rpc": "/mcp/analyst/rpc",
        }

    # MCP at root path for MCP Inspector compatibility
    @app.post("/")
    async def mcp_root_post_handler(request: Request):
        """Handle MCP POST at root for MCP Inspector."""
        from foggy.mcp.routers.mcp_rpc import _handle_streamable_post
        from foggy.mcp.routers.mcp_rpc import McpJsonRpcRequest

        async def handle_request(req: McpJsonRpcRequest):
            return await _create_handle_request(service, accessor, req)

        return await _handle_streamable_post(request, handle_request)

    # SSE endpoint at root for MCP Inspector
    @app.get("/sse")
    async def mcp_sse_root(request: Request):
        """SSE endpoint for MCP Inspector."""
        from foggy.mcp.routers.mcp_rpc import _handle_sse_stream
        return await _handle_sse_stream(request)

    # MCP Inspector compatible endpoint - handles both GET and POST at same URL
    @app.api_route("/mcp", methods=["GET", "POST"])
    async def mcp_inspector_endpoint(request: Request):
        """MCP Inspector compatible endpoint.

        MCP Inspector uses this pattern:
        - GET: Establish SSE connection
        - POST: Send JSON-RPC requests
        """
        from foggy.mcp.routers.mcp_rpc import (
            _handle_sse_stream,
            _handle_streamable_post,
            McpJsonRpcRequest
        )

        if request.method == "GET":
            return await _handle_sse_stream(request)

        # POST - handle JSON-RPC
        async def handle_request(req: McpJsonRpcRequest):
            return await _create_handle_request(service, accessor, req)

        return await _handle_streamable_post(request, handle_request)

    # REST API endpoints
    @app.get("/api/v1/models")
    async def list_models():
        return {"models": service.get_all_model_names()}

    @app.get("/api/v1/models/{model_name}")
    async def get_model(model_name: str):
        from foggy.mcp_spi import SemanticMetadataRequest
        request = SemanticMetadataRequest(model=model_name)
        response = service.get_metadata(request)
        if response.error:
            return {"error": response.error}
        return response.model_dump()

    @app.post("/api/v1/query/{model_name}")
    async def query_model(model_name: str, payload: dict):
        response = accessor.query_model(model_name, payload)
        return response.model_dump()

    # Include MCP RPC router at /mcp/analyst
    mcp_router = create_mcp_router(service, accessor)
    app.include_router(mcp_router, prefix="/mcp/analyst")

    return app, service, accessor


async def _create_handle_request(service, accessor, request):
    """Create handle_request function for MCP."""
    from foggy.mcp.routers.mcp_rpc import (
        McpJsonRpcResponse, McpResource, McpTool,
        QUERY_TOOL, METADATA_TOOL, LIST_MODELS_TOOL, VALIDATE_QUERY_TOOL
    )
    from foggy.mcp_spi import SemanticMetadataRequest
    import json

    TOOLS = [QUERY_TOOL, METADATA_TOOL, LIST_MODELS_TOOL, VALIDATE_QUERY_TOOL]

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

            if tool_name == "list_models":
                models = service.get_all_model_names()
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

            elif tool_name == "get_metadata":
                model_name = tool_args.get("model")
                if not model_name:
                    return McpJsonRpcResponse(
                        id=request.id,
                        error={"code": -32602, "message": "model parameter required"}
                    )

                meta_request = SemanticMetadataRequest(
                    model=model_name,
                    include_dimensions=tool_args.get("include_dimensions", True),
                    include_measures=tool_args.get("include_measures", True),
                )
                response = service.get_metadata(meta_request)

                if response.error:
                    return McpJsonRpcResponse(
                        id=request.id,
                        error={"code": -32602, "message": response.error}
                    )

                return McpJsonRpcResponse(
                    id=request.id,
                    result={
                        "content": [{
                            "type": "text",
                            "text": json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
                        }]
                    }
                )

            elif tool_name == "query_model":
                model_name = tool_args.get("model")
                if not model_name:
                    return McpJsonRpcResponse(
                        id=request.id,
                        error={"code": -32602, "message": "model parameter required"}
                    )

                # V3 format: pass payload through as-is
                payload = tool_args.get("payload", {})
                if not payload:
                    # Flat format fallback
                    payload = {
                        "columns": tool_args.get("columns", []),
                        "slice": tool_args.get("slice", []),
                        "groupBy": tool_args.get("groupBy", []),
                        "orderBy": tool_args.get("orderBy", []),
                        "limit": tool_args.get("limit", 100),
                        "start": tool_args.get("start", 0),
                    }

                response = accessor.query_model(model_name, payload)

                result_data = _json_serializable(
                    response.model_dump(by_alias=True, exclude_none=True)
                )

                if response.error:
                    result_data["error"] = response.error
                if response.warnings:
                    result_data["warnings"] = response.warnings

                return McpJsonRpcResponse(
                    id=request.id,
                    result={
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result_data, ensure_ascii=False, indent=2)
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
            models = service.get_all_model_names()
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
        logging.exception(f"MCP request failed: {e}")
        return McpJsonRpcResponse(
            id=request.id,
            error={"code": -32603, "message": str(e)}
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Start Foggy MCP Demo Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    logger.info("Creating sample database...")
    executor = asyncio.run(create_sample_database())
    logger.info("Sample database created")

    logger.info("Creating FastAPI application...")
    app, service, accessor = create_app_with_sample_data(executor)
    logger.info(f"Registered models: {service.get_all_model_names()}")

    # Run server
    import uvicorn
    logger.info(f"Starting server on {args.host}:{args.port}")
    logger.info(f"API docs: http://{args.host}:{args.port}/docs")
    logger.info(f"MCP RPC endpoint: http://{args.host}:{args.port}/mcp/analyst/rpc")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()