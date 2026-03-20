"""One-click demo: start MCP server connected to Java Docker MySQL.

Usage:
    python -m foggy.demo.run_demo
    python -m foggy.demo.run_demo --port 8066
    python -m foggy.demo.run_demo --db-host 192.168.1.100 --db-port 3306

Default connects to: localhost:13306 (foggy Docker MySQL)
"""

import sys
import os

# Add src to path if running directly
src_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if src_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(src_dir))


def main():
    """Launch the MCP demo server."""
    import argparse
    import logging
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Foggy MCP Demo Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8066, help="Server port")
    parser.add_argument("--db-host", default="localhost", help="MySQL host")
    parser.add_argument("--db-port", type=int, default=13306, help="MySQL port")
    parser.add_argument("--db-user", default="foggy", help="MySQL user")
    parser.add_argument("--db-password", default="foggy_test_123", help="MySQL password")
    parser.add_argument("--db-name", default="foggy_test", help="MySQL database")
    parser.add_argument("--reload", action="store_true", help="Auto-reload")
    args = parser.parse_args()

    from foggy.mcp.launcher.app import create_app, _app_config
    from foggy.mcp.config.properties import McpProperties
    from foggy.mcp.config.datasource import DataSourceConfig, DataSourceType

    properties = McpProperties(host=args.host, port=args.port)

    data_source_configs = [
        DataSourceConfig(
            name="default",
            source_type=DataSourceType.MYSQL,
            host=args.db_host,
            port=args.db_port,
            database=args.db_name,
            username=args.db_user,
            password=args.db_password,
        )
    ]

    # Store in module config for factory
    _app_config["properties"] = properties
    _app_config["data_source_configs"] = data_source_configs
    _app_config["load_demo_models"] = True

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Foggy MCP Server (Python) - Demo Mode              ║
╠══════════════════════════════════════════════════════════════╣
║  Server:   http://{args.host}:{args.port}                            ║
║  MySQL:    {args.db_host}:{args.db_port}/{args.db_name:<20}       ║
║  Docs:     http://localhost:{args.port}/docs                       ║
║  MCP RPC:  http://localhost:{args.port}/mcp/analyst/rpc            ║
╠══════════════════════════════════════════════════════════════╣
║  Test:                                                       ║
║    curl http://localhost:{args.port}/api/v1/models                 ║
║    curl http://localhost:{args.port}/api/v1/models/FactSalesModel  ║
╚══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "foggy.mcp.launcher.app:_create_app_from_config",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
