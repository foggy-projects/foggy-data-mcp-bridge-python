"""Unit tests for MCP server components."""

import pytest
from datetime import datetime

# Config tests
from foggy.mcp.config.properties import McpProperties, AuthProperties, PerformanceInfo
from foggy.mcp.config.datasource import DataSourceConfig, DataSourceManager, DataSourceType

# Schema tests
from foggy.mcp.schema.request import McpRequest, McpRequestContext, QueryRequest
from foggy.mcp.schema.response import McpResponse, McpError, QueryResult, ResponseStatus
from foggy.mcp.schema.query import DatasetNLQueryRequest, DatasetNLQueryResponse, QueryIntent
from foggy.mcp.schema.tool import ToolCallRequest, ToolCallResult, ToolDefinition, ToolCallStatus

# Service tests
from foggy.mcp.services.mcp_service import LocalDatasetAccessor, SemanticServiceResolverImpl
from foggy.mcp.services.tool_dispatcher import McpToolDispatcher, tool
from foggy.mcp.services.query_service import QueryService

# Tool tests
from foggy.mcp.tools.base import BaseMcpTool, ToolRegistry
from foggy.mcp.tools.query_tool import QueryModelTool
from foggy.mcp.tools.metadata_tool import MetadataTool, ListModelsTool

# Auth tests
from foggy.mcp.auth.context import AuthContext, UserRole
from foggy.mcp.auth.interceptor import NoAuthInterceptor, ApiKeyInterceptor, RoleBasedAuthorizer

# Audit tests
from foggy.mcp.audit.service import ToolAuditService, ToolAuditLog, AuditEventType, AuditLogLevel

# Storage tests
from foggy.mcp.storage.properties import ChartStorageProperties, StorageType
from foggy.mcp.storage.adapter import LocalChartStorageAdapter, ChartMetadata


class TestMcpProperties:
    """Tests for MCP properties."""

    def test_default_properties(self):
        """Test default property values."""
        props = McpProperties()
        assert props.server_name == "foggy-mcp"
        assert props.server_version == "1.0.0"
        assert props.port == 8080
        assert props.enable_query_tools is True

    def test_custom_properties(self):
        """Test custom property values."""
        props = McpProperties(
            server_name="custom-mcp",
            port=9000,
            max_query_rows=50000
        )
        assert props.server_name == "custom-mcp"
        assert props.port == 9000
        assert props.max_query_rows == 50000


class TestAuthProperties:
    """Tests for auth properties."""

    def test_default_auth_disabled(self):
        """Test default auth is disabled."""
        props = AuthProperties()
        assert props.enabled is False
        assert props.auth_type == "none"

    def test_api_key_auth(self):
        """Test API key auth configuration."""
        props = AuthProperties(
            enabled=True,
            auth_type="api_key",
            api_keys=["key1", "key2"]
        )
        assert props.enabled is True
        assert len(props.api_keys) == 2


class TestDataSourceConfig:
    """Tests for data source configuration."""

    def test_mysql_config(self):
        """Test MySQL data source configuration."""
        config = DataSourceConfig(
            name="test_mysql",
            source_type=DataSourceType.MYSQL,
            host="localhost",
            port=3306,
            database="test_db",
            username="user",
            password="pass"
        )
        url = config.get_connection_url()
        assert "mysql+aiomysql" in url
        assert "localhost:3306" in url
        assert "test_db" in url

    def test_postgres_config(self):
        """Test PostgreSQL data source configuration."""
        config = DataSourceConfig(
            name="test_pg",
            source_type=DataSourceType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test_db",
            username="user",
            password="pass"
        )
        url = config.get_connection_url()
        assert "postgresql+asyncpg" in url

    def test_sqlite_config(self):
        """Test SQLite data source configuration."""
        config = DataSourceConfig(
            name="test_sqlite",
            source_type=DataSourceType.SQLITE,
            database="/path/to/db.sqlite"
        )
        url = config.get_connection_url()
        assert "sqlite+aiosqlite" in url


class TestDataSourceManager:
    """Tests for data source manager."""

    def test_register_datasource(self):
        """Test registering a data source."""
        manager = DataSourceManager()
        config = DataSourceConfig(
            name="test",
            source_type=DataSourceType.SQLITE,
            database=":memory:"
        )
        manager.register(config)
        assert "test" in manager.list_names()

    def test_default_datasource(self):
        """Test default data source setting."""
        manager = DataSourceManager()
        config = DataSourceConfig(
            name="default",
            source_type=DataSourceType.SQLITE,
            database=":memory:"
        )
        manager.register(config, set_default=True)
        assert manager.default_source == "default"

    def test_get_datasource(self):
        """Test getting a data source."""
        manager = DataSourceManager()
        config = DataSourceConfig(
            name="test",
            source_type=DataSourceType.SQLITE,
            database=":memory:"
        )
        manager.register(config)
        retrieved = manager.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"


class TestMcpRequest:
    """Tests for MCP request schema."""

    def test_create_request(self):
        """Test creating a request."""
        request = McpRequest(
            method="query",
            params={"model": "test_model"}
        )
        assert request.method == "query"
        assert request.get_param("model") == "test_model"

    def test_request_context(self):
        """Test request context."""
        context = McpRequestContext(
            user_id="user123",
            user_roles=["admin", "analyst"]
        )
        assert context.user_id == "user123"
        assert "admin" in context.user_roles


class TestMcpResponse:
    """Tests for MCP response schema."""

    def test_success_response(self):
        """Test successful response."""
        response = McpResponse.success(
            result={"data": [1, 2, 3]},
            request_id="req123"
        )
        assert response.is_success()
        assert response.result["data"] == [1, 2, 3]

    def test_error_response(self):
        """Test error response."""
        error = McpError.query_error("Query failed")
        response = McpResponse.failure(error, request_id="req123")
        assert not response.is_success()
        assert response.error.message == "Query failed"


class TestMcpError:
    """Tests for MCP error object."""

    def test_error_codes(self):
        """Test error code constants."""
        assert McpError.PARSE_ERROR == -32700
        assert McpError.INVALID_REQUEST == -32600
        assert McpError.METHOD_NOT_FOUND == -32601

    def test_factory_methods(self):
        """Test error factory methods."""
        err = McpError.method_not_found("unknown_method")
        assert err.code == McpError.METHOD_NOT_FOUND
        assert "unknown_method" in err.message


class TestQueryRequest:
    """Tests for query request schema."""

    def test_query_request(self):
        """Test query request creation."""
        request = QueryRequest(
            query_model="sales_qm",
            select=["date", "amount"],
            where="amount > 100",
            limit=100
        )
        assert request.query_model == "sales_qm"
        assert len(request.select) == 2
        assert request.limit == 100


class TestQueryResult:
    """Tests for query result schema."""

    def test_query_result(self):
        """Test query result creation."""
        result = QueryResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
            total_rows=2
        )
        assert len(result.columns) == 2
        assert result.total_rows == 2


class TestToolCallRequest:
    """Tests for tool call request schema."""

    def test_tool_call_request(self):
        """Test tool call request creation."""
        request = ToolCallRequest(
            tool_name="query_model",
            arguments={"model": "test"}
        )
        assert request.tool_name == "query_model"
        assert request.get_argument("model") == "test"


class TestToolCallResult:
    """Tests for tool call result schema."""

    def test_success_result(self):
        """Test successful tool result."""
        result = ToolCallResult.success_result(
            tool_name="test_tool",
            result={"data": "value"},
            duration_ms=123.45
        )
        assert result.is_success()
        assert result.duration_ms == 123.45

    def test_failure_result(self):
        """Test failed tool result."""
        result = ToolCallResult.failure_result(
            tool_name="test_tool",
            error_message="Tool failed"
        )
        assert not result.is_success()
        assert result.error_message == "Tool failed"


class TestToolDefinition:
    """Tests for tool definition schema."""

    def test_tool_definition(self):
        """Test tool definition creation."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            category="query",
            parameters=[
                {"name": "model", "type": "string", "required": True}
            ]
        )
        assert tool_def.name == "test_tool"
        assert len(tool_def.parameters) == 1

    def test_to_openai_format(self):
        """Test OpenAI format conversion."""
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                {"name": "model", "type": "string", "required": True, "description": "Model name"}
            ]
        )
        openai_format = tool_def.to_openai_tool()
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "test_tool"


class TestToolDispatcher:
    """Tests for tool dispatcher."""

    def test_register_tool(self):
        """Test tool registration."""
        dispatcher = McpToolDispatcher()

        @tool(name="test_tool")
        async def my_tool(arg1: str) -> str:
            """Test tool."""
            return f"result: {arg1}"

        dispatcher.register("test_tool", my_tool)
        tools = dispatcher.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    def test_sync_tool(self):
        """Test synchronous tool registration."""
        dispatcher = McpToolDispatcher()

        def sync_tool(arg1: str) -> str:
            """Sync tool."""
            return f"result: {arg1}"

        dispatcher.register("sync_tool", sync_tool)
        tool = dispatcher.get_tool("sync_tool")
        assert tool is not None


class TestLocalDatasetAccessor:
    """Tests for local dataset accessor."""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test listing models."""
        accessor = LocalDatasetAccessor()
        await accessor.initialize()
        models = await accessor.list_models()
        assert models == []
        await accessor.shutdown()

    @pytest.mark.asyncio
    async def test_register_model(self):
        """Test registering a model."""
        accessor = LocalDatasetAccessor()
        await accessor.initialize()
        accessor.register_model("test_model", {"name": "test_model"})
        models = await accessor.list_models()
        assert "test_model" in models
        await accessor.shutdown()


class TestAuthContext:
    """Tests for authentication context."""

    def test_anonymous_context(self):
        """Test anonymous context."""
        ctx = AuthContext.anonymous()
        assert ctx.authenticated is False
        assert ctx.user_id == "anonymous"

    def test_system_context(self):
        """Test system context."""
        ctx = AuthContext.system()
        assert ctx.authenticated is True
        assert ctx.is_admin()

    def test_role_checking(self):
        """Test role checking."""
        ctx = AuthContext(
            user_id="user1",
            roles=["analyst", "business"],
            authenticated=True
        )
        assert ctx.has_role("analyst")
        assert ctx.has_any_role(["admin", "analyst"])
        assert not ctx.has_role("admin")


class TestNoAuthInterceptor:
    """Tests for no-auth interceptor."""

    @pytest.mark.asyncio
    async def test_always_authenticated(self):
        """Test that no-auth always allows access."""
        interceptor = NoAuthInterceptor()
        ctx = await interceptor.authenticate({})
        assert ctx.authenticated is False  # Anonymous

        authorized = await interceptor.authorize(ctx, "resource", "action")
        assert authorized is True


class TestApiKeyInterceptor:
    """Tests for API key interceptor."""

    @pytest.mark.asyncio
    async def test_valid_key(self):
        """Test valid API key authentication."""
        interceptor = ApiKeyInterceptor()
        interceptor.add_key("test-key", AuthContext(
            user_id="user1",
            roles=["analyst"],
            authenticated=True
        ))

        ctx = await interceptor.authenticate({
            "headers": {"X-API-Key": "test-key"}
        })
        assert ctx.authenticated is True
        assert ctx.user_id == "user1"

    @pytest.mark.asyncio
    async def test_invalid_key(self):
        """Test invalid API key authentication."""
        interceptor = ApiKeyInterceptor()

        ctx = await interceptor.authenticate({
            "headers": {"X-API-Key": "invalid-key"}
        })
        assert ctx.authenticated is False


class TestRoleBasedAuthorizer:
    """Tests for role-based authorizer."""

    def test_admin_permission(self):
        """Test admin has full access."""
        authorizer = RoleBasedAuthorizer()
        ctx = AuthContext(roles=[UserRole.ADMIN], authenticated=True)

        assert authorizer.check_permission(ctx, "any:permission")

    def test_analyst_permission(self):
        """Test analyst permissions."""
        authorizer = RoleBasedAuthorizer()
        ctx = AuthContext(roles=[UserRole.ANALYST], authenticated=True)

        assert authorizer.check_permission(ctx, "query:read")
        assert authorizer.check_permission(ctx, "metadata:read")
        assert not authorizer.check_permission(ctx, "admin:write")


class TestToolAuditService:
    """Tests for tool audit service."""

    def test_log_tool_call(self):
        """Test logging a tool call."""
        service = ToolAuditService()
        log_id = service.log_tool_call(
            tool_name="test_tool",
            arguments={"arg1": "value1"},
            user_id="user1"
        )
        assert log_id is not None

        logs = service.get_logs(tool_name="test_tool")
        assert len(logs) == 1

    def test_log_success(self):
        """Test logging successful execution."""
        service = ToolAuditService()
        log_id = service.log_tool_call("test_tool", {})

        service.log_tool_success(log_id, duration_ms=100.5)

        logs = service.get_logs(tool_name="test_tool")
        assert logs[0].success is True
        assert logs[0].duration_ms == 100.5

    def test_log_failure(self):
        """Test logging failed execution."""
        service = ToolAuditService()
        log_id = service.log_tool_call("test_tool", {})

        service.log_tool_failure(log_id, error_message="Failed", error_code=500)

        logs = service.get_logs(tool_name="test_tool")
        assert logs[0].success is False
        assert logs[0].error_message == "Failed"

    def test_get_stats(self):
        """Test getting statistics."""
        service = ToolAuditService()

        # Log some calls
        log_id1 = service.log_tool_call("tool1", {})
        service.log_tool_success(log_id1, 100)

        log_id2 = service.log_tool_call("tool2", {})
        service.log_tool_failure(log_id2, "Error")

        stats = service.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1


class TestChartStorageProperties:
    """Tests for chart storage properties."""

    def test_default_properties(self):
        """Test default storage properties."""
        props = ChartStorageProperties()
        assert props.storage_type == StorageType.LOCAL
        assert props.default_format == "png"
        assert props.retention_days == 30


class TestLocalChartStorageAdapter:
    """Tests for local chart storage adapter."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        """Test storing and retrieving a chart."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            props = ChartStorageProperties(
                storage_type=StorageType.LOCAL,
                local_path=tmpdir
            )
            adapter = LocalChartStorageAdapter(props)

            # Store chart
            chart_data = b"fake image data"
            metadata = await adapter.store(chart_data, format="png")

            assert metadata.chart_id is not None
            assert metadata.format == "png"
            assert metadata.file_size == len(chart_data)

            # Retrieve chart
            retrieved = await adapter.retrieve(metadata.chart_id)
            assert retrieved == chart_data

    @pytest.mark.asyncio
    async def test_delete_chart(self):
        """Test deleting a chart."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            props = ChartStorageProperties(local_path=tmpdir)
            adapter = LocalChartStorageAdapter(props)

            metadata = await adapter.store(b"data", format="png")
            assert await adapter.exists(metadata.chart_id)

            deleted = await adapter.delete(metadata.chart_id)
            assert deleted is True
            assert not await adapter.exists(metadata.chart_id)


class TestToolRegistry:
    """Tests for tool registry."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = QueryModelTool()
        registry.register(tool)

        assert registry.get("query_model") is not None
        assert len(registry.list_tools()) == 1

    def test_list_by_category(self):
        """Test listing tools by category."""
        from foggy.mcp_spi.tool import ToolCategory

        registry = ToolRegistry()
        registry.register(QueryModelTool())
        registry.register(MetadataTool())

        query_tools = registry.list_by_category(ToolCategory.QUERY)
        assert len(query_tools) >= 1

    def test_to_openai_tools(self):
        """Test exporting to OpenAI format."""
        registry = ToolRegistry()
        registry.register(QueryModelTool())

        openai_tools = registry.to_openai_tools()
        assert len(openai_tools) >= 1
        assert openai_tools[0]["type"] == "function"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])