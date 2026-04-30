from __future__ import annotations

import pytest
from typing import Any

from foggy.mcp.tools.compose_script_tool import ComposeScriptTool
from foggy.mcp_spi.context import ToolExecutionContext
from foggy.dataset_model.engine.compose.security.error_codes import (
    MODEL_BINDING_MISSING,
    INVALID_RESPONSE,
    PRINCIPAL_MISMATCH,
)
from foggy.dataset_model.semantic.service import SemanticQueryService
from foggy.demo.models.ecommerce_models import create_fact_sales_model

def _resolver_factory(_ctx):
    # Dummy built-in resolver that always allows
    from foggy.dataset_model.engine.compose.security import AuthorityResolution, ModelBinding
    class DummyResolver:
        def resolve(self, request):
            return AuthorityResolution(bindings={
                mq.model: ModelBinding() for mq in request.models
            })
    return DummyResolver()

def _tool_ctx(namespace="odoo", user_id="u1", tenant_id="t1", remote_compose="1") -> ToolExecutionContext:
    return ToolExecutionContext(
        request_id="req-1",
        namespace=namespace,
        headers={
            "X-User-Id": user_id,
            "X-Tenant-Id": tenant_id,
            "X-Foggy-Remote-Compose": remote_compose,
        },
    )

class _DummyExecutor:
    def __init__(self):
        self.sql = None
    async def execute(self, sql, params, **kwargs):
        self.sql = sql
        return [{"id": 1}]

@pytest.fixture
def tool():
    svc = SemanticQueryService()
    svc.register_model(create_fact_sales_model())
    executor = _DummyExecutor()
    svc.set_executor(executor)
    t = ComposeScriptTool(
        authority_resolver_factory=_resolver_factory,
        semantic_service=svc,
    )
    t.executor = executor # save for tests
    return t

@pytest.mark.asyncio
async def test_odoo_remote_compose_normal_path(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "FactSalesModel": {
                "fieldAccess": None,
                "deniedColumns": [],
                "systemSlice": [{"field": "customer$id", "op": "eq", "value": 42}]
            }
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["orderId$caption", "salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    # Should succeed and compile SQL with customer$id filter
    assert result.success is True
    sql = tool.executor.sql
    assert sql is not None
    assert "42" in sql or "customer_key" in sql.lower() or "customer" in sql.lower()
    assert "__foggyAuthorityBinding" not in arguments

@pytest.mark.asyncio
async def test_odoo_remote_compose_denied_columns_blocks_query(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "FactSalesModel": {
                "fieldAccess": None,
                "deniedColumns": [{"table": "fact_sales", "column": "sales_amount"}],
                "systemSlice": []
            }
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["orderId$caption", "salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    # It passes authority-resolve, but fails at compile because salesAmount is blocked
    assert result.success is False
    assert result.data["phase"] == "compile"
    assert "salesAmount" in str(result.data)

@pytest.mark.asyncio
async def test_odoo_remote_compose_denied_calculated_field(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "FactSalesModel": {
                "fieldAccess": None,
                "deniedColumns": [{"table": "fact_sales", "column": "discount_amount"}],
                "systemSlice": []
            }
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", calculatedFields: [{name: "net", expression: "salesAmount - discountAmount"}], columns: ["orderId$caption", "net"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["phase"] == "compile"
    assert "discountAmount" in str(result.data)

@pytest.mark.asyncio
async def test_odoo_remote_compose_malformed_denied_columns(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "FactSalesModel": {
                "fieldAccess": None,
                "deniedColumns": {"table": "fact_sales", "column": "sales_amount"}, # Should be list
                "systemSlice": []
            }
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["phase"] in ("authority-resolve", "permission-resolve")
    assert result.data["error_code"] == INVALID_RESPONSE

@pytest.mark.asyncio
async def test_odoo_remote_compose_missing_envelope_fails(tool):
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
    }
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["phase"] in ("authority-resolve", "permission-resolve")
    assert "Missing __foggyAuthorityBinding" in result.data["message"]

@pytest.mark.asyncio
async def test_odoo_remote_compose_missing_model_fails(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "Y": {} # binding for Y, but script queries FactSalesModel
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["error_code"] == MODEL_BINDING_MISSING

@pytest.mark.asyncio
async def test_odoo_remote_compose_invalid_issuer(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "unknown-issuer",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {"FactSalesModel": {}}
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["error_code"] == INVALID_RESPONSE
    assert "issuer" in result.data["message"].lower()

@pytest.mark.asyncio
async def test_odoo_remote_compose_tenant_mismatch(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t2"}, # ctx has t1
        "bindings": {"FactSalesModel": {}}
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["error_code"] == PRINCIPAL_MISMATCH

@pytest.mark.asyncio
async def test_non_odoo_mcp_call_ignores_envelope(tool):
    # Envelope is completely broken (no principal, wrong issuer) which would fail if evaluated
    envelope = {
        "issuer": "evil-hacker",
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    # Non-odoo context (no remote-compose header)
    ctx = _tool_ctx(remote_compose="")
    result = await tool.execute(arguments, ctx)
    
    # Built-in resolver allows it, envelope is completely ignored, successfully executes
    assert result.success is True
    assert tool.executor.sql is not None
    # Binding envelope should still be removed from params to not leak
    assert "__foggyAuthorityBinding" not in arguments

@pytest.mark.asyncio
async def test_odoo_remote_compose_empty_denied_columns_fails(tool):
    envelope = {
        "version": "foggy.compose.authority-binding.v1",
        "issuer": "foggy-odoo-bridge-pro",
        "namespace": "odoo",
        "principal": {"userId": "u1", "tenantId": "t1"},
        "bindings": {
            "FactSalesModel": {
                "fieldAccess": None,
                "deniedColumns": [{"table": "fact_sales", "column": "   "}], # whitespace column
                "systemSlice": []
            }
        }
    }
    arguments = {
        "script": 'from({model: "FactSalesModel", columns: ["salesAmount"]}).execute()',
        "__foggyAuthorityBinding": envelope
    }
    
    ctx = _tool_ctx()
    result = await tool.execute(arguments, ctx)
    
    assert result.success is False
    assert result.data["phase"] in ("authority-resolve", "permission-resolve")
    assert result.data["error_code"] == INVALID_RESPONSE
    assert "must be a non-empty string" in result.data["message"].lower()
