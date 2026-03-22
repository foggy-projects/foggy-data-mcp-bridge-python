# Foggy Data MCP Bridge — Python

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1322%20passed-brightgreen.svg)]()

A semantic layer query engine with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) support, enabling AI assistants to query structured data through natural, declarative interfaces.

Ported from [foggy-data-mcp-bridge](../foggy-data-mcp-bridge/) (Java), maintaining full API compatibility.

## What It Does

**Foggy Data MCP Bridge** sits between your database and AI assistants (Claude, GPT, etc.), providing:

- **Semantic Layer** — Define business-friendly models (dimensions, measures, calculated fields) on top of raw SQL tables. AI queries "sales by region" instead of writing complex JOINs.
- **MCP Protocol** — Exposes data through the [Model Context Protocol](https://modelcontextprotocol.io/), so AI assistants can discover and query your data models natively.
- **Multi-Database** — Works with MySQL, PostgreSQL, and SQLite through async drivers.
- **Embeddable** — Can be vendored into host applications (e.g., Odoo) as a lightweight in-process engine, no separate server required.

```
┌─────────────────┐     MCP / REST      ┌───────────────────────┐
│  AI Assistant    │ ◄──────────────────► │  Foggy MCP Bridge     │
│  (Claude, etc.)  │   JSON-RPC 2.0      │  ┌─────────────────┐  │
└─────────────────┘                      │  │ Semantic Layer   │  │
                                         │  │ TM/QM Models     │  │
┌─────────────────┐     Async SQL        │  └────────┬────────┘  │
│  Database        │ ◄──────────────────► │           │           │
│  MySQL/PG/SQLite │   aiomysql/asyncpg   │  SQL Query Engine    │
└─────────────────┘                      └───────────────────────┘
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/foggy-projects/foggy-data-mcp-bridge-python.git
cd foggy-data-mcp-bridge-python

# Install with development dependencies
pip install -e ".[dev]"

# Install database driver(s) you need
pip install aiomysql    # MySQL
pip install asyncpg     # PostgreSQL
pip install aiosqlite   # SQLite (included by default)
```

### Run the Demo Server

```bash
# Start with in-memory SQLite demo data
python -m foggy.demo.run_demo --port 8066

# Or connect to an existing database
python -m foggy.mcp.launcher.app \
  --db-host localhost --db-port 5432 \
  --db-user foggy --db-password secret \
  --db-name mydb
```

Then open http://localhost:8066/docs for the Swagger UI.

### Run Tests

```bash
python -m pytest --tb=short -q
# 1322 passed, 76 skipped
```

## Architecture

### Module Dependency Graph

```
foggy.mcp (MCP Server, FastAPI)
    │
    ├──► foggy.dataset_model (Semantic Query Engine)
    │        ├──► foggy.dataset (SQL Generation, DB Execution)
    │        │        └──► foggy.core (Utilities, Exceptions)
    │        └──► foggy.fsscript (Expression Engine)
    │
    └──► foggy.mcp_spi (SPI Types — shared interface layer)
```

Each layer has strict dependency boundaries — no circular imports, no upward dependencies.

### Project Structure

```
src/foggy/
├── core/                # Utilities, exceptions, filters
├── bean_copy/           # Bean/Map conversion utilities
├── mcp_spi/             # SPI types (shared between all layers)
│   ├── semantic.py      # SemanticQueryRequest/Response (Java-aligned Pydantic models)
│   ├── accessor.py      # DatasetAccessor, LocalDatasetAccessor
│   ├── enums.py         # QueryMode, MetadataFormat, AccessMode
│   └── tool.py          # McpTool, ToolResult
├── dataset/             # Database abstraction layer
│   ├── dialects/        # MySQL, PostgreSQL, SQLite, SQL Server
│   ├── db/              # Async executor, connection management
│   └── resultset/       # Record, RecordList
├── dataset_model/       # Semantic layer engine
│   ├── semantic/        # SemanticQueryService (core query engine)
│   ├── engine/          # SQL query builder, formula engine, JOIN graph
│   ├── definitions/     # Model definitions (TM/QM)
│   └── impl/            # Model implementations
├── fsscript/            # FSScript expression engine (ported from Java)
├── mcp/                 # MCP server (FastAPI)
│   ├── launcher/        # Application factory, server startup
│   ├── routers/         # HTTP routes (admin, analyst, mcp_rpc, semantic_v3)
│   ├── schemas/         # MCP tool definitions (JSON schema + Markdown)
│   ├── tools/           # Tool implementations (query, metadata, chart)
│   ├── config/          # DataSource, Properties
│   └── audit/           # Tool audit logging
└── demo/                # Demo models and startup scripts
```

## API Reference

### MCP Protocol (for AI Assistants)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp/analyst/rpc` | POST | MCP Streamable HTTP (JSON-RPC 2.0) |
| `/mcp/analyst/rpc` | GET | SSE stream for server-sent events |

### REST API (for Applications)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/models` | GET | List all available models |
| `/api/v1/models/{name}` | GET | Get model metadata |
| `/api/v1/query/{name}` | POST | Execute a query |
| `/api/v1/query/{name}/validate` | POST | Validate query without executing |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |

### MCP Tools

| Tool | Description | Status |
|------|-------------|--------|
| `dataset.get_metadata` | Get V3 metadata for all models and fields | ✅ |
| `dataset.describe_model_internal` | Get detailed metadata for a specific model | ✅ |
| `dataset.query_model` | Execute a semantic query (V3 payload format) | ✅ |
| `dataset_nl.query` | Natural language query | ⏳ |
| `dataset.compose_query` | FSScript multi-model orchestration | ⏳ |

## Usage Examples

### Query via REST API

```bash
# List models
curl http://localhost:8066/api/v1/models

# Query a model
curl -X POST http://localhost:8066/api/v1/query/sales_model \
  -H "Content-Type: application/json" \
  -d '{
    "columns": ["product_name", "total_amount"],
    "slice": [{"field": "status", "op": "eq", "value": "confirmed"}],
    "groupBy": ["product_name"],
    "orderBy": [{"field": "total_amount", "direction": "DESC"}],
    "limit": 50
  }'
```

### Embedded Mode (No Server)

```python
from foggy.mcp_spi import LocalDatasetAccessor
from foggy.dataset_model.semantic import SemanticQueryService

# Initialize the engine
service = SemanticQueryService(executor=my_db_executor, dialect=my_dialect)
service.register_model(my_table_model)

# Create accessor (accepts standard JSON dict)
accessor = LocalDatasetAccessor(service)

# Query with plain dict — no need to construct typed objects
result = accessor.query_model("sales_model", {
    "columns": ["product_name", "total_amount"],
    "groupBy": ["product_name"],
    "orderBy": [{"field": "total_amount", "direction": "DESC"}],
    "limit": 10,
})

# Result is a Pydantic model, serialize to Java-compatible JSON
print(result.model_dump(by_alias=True, exclude_none=True))
```

### MCP Tool Call (JSON-RPC 2.0)

```bash
curl -X POST http://localhost:8066/mcp/analyst/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "dataset.query_model",
      "arguments": {
        "model": "sales_model",
        "payload": {
          "columns": ["product_name", "total_amount"],
          "limit": 10
        }
      }
    }
  }'
```

## Database Support

| Database | Driver | Dialect | Status |
|----------|--------|---------|--------|
| MySQL | aiomysql | `MysqlDialect` | ✅ Full support |
| PostgreSQL | asyncpg | `PostgresDialect` | ✅ Full support |
| SQLite | aiosqlite | `SqliteDialect` | ✅ Full support |
| SQL Server | — | `SqlServerDialect` | 🔧 Dialect only |

All database operations are fully async. SQL identifier quoting is dialect-aware (backticks for MySQL, double-quotes for PostgreSQL/SQLite, brackets for SQL Server).

## Syncing with Java

Tool definitions (JSON schema + Markdown descriptions) are shared between Java and Python implementations:

```bash
# Sync tool definitions from Java project
python scripts/sync_mcp_schemas.py

# Preview changes without applying
python scripts/sync_mcp_schemas.py --dry-run

# Show diff only
python scripts/sync_mcp_schemas.py --diff
```

## Development

### Prerequisites

- Python 3.11+
- A database (or use the built-in SQLite demo)

### Code Standards

- **Type annotations** on all public APIs
- **Pydantic v2** for data models with Java-aligned camelCase aliases
- **Async I/O** for all database operations
- **No `eval()`** — SQL parameters use placeholders, never string concatenation
- **pytest** tests required for all new features

### Running Checks

```bash
# Tests
python -m pytest --tb=short -q

# Type checking
mypy src/foggy/

# Linting
ruff check src/ tests/
```

## Vendoring (Embedded Use)

For embedding in host applications (e.g., Odoo), vendor the minimal module set:

```
lib/foggy/
  ├── core/          ✅ Required
  ├── mcp_spi/       ✅ Required (SPI types + Accessor)
  ├── dataset/       ✅ Required (SQL engine)
  ├── dataset_model/ ✅ Required (Semantic engine)
  ├── fsscript/      ✅ Required (Expression engine)
  ├── bean_copy/     ✅ Required (Utilities)
  └── mcp/           ❌ Not needed (MCP Server, only for standalone deployment)
```

## License

[Apache License 2.0](LICENSE)
