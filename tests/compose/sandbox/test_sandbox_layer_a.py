"""Layer A sandbox tests (Host layer)."""

import pytest

from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal
from foggy.dataset_model.engine.compose.sandbox.error_codes import (
    LAYER_A_ASYNC_DENIED,
    LAYER_A_CONTEXT_ACCESS,
    LAYER_A_EVAL_DENIED,
    LAYER_A_GLOBAL_DENIED,
    LAYER_A_IO_DENIED,
    LAYER_A_NETWORK_DENIED,
    LAYER_A_SECURITY_PARAM,
    LAYER_A_TIME_DENIED,
)
from foggy.dataset_model.engine.compose.sandbox.exceptions import (
    ComposeSandboxViolationError,
)

from .compose_sandbox_test_support import SandboxRunner, assert_sandbox_violation


from foggy.dataset_model.engine.compose.security.models import AuthorityResolution, ModelBinding

class MockResolver:
    def resolve(self, request, *args, **kwargs):
        bindings = {m.model: ModelBinding() for m in request.models}
        return AuthorityResolution(bindings=bindings)

@pytest.fixture
def runner():
    ctx = ComposeQueryContext(
        principal=Principal(user_id="u1", tenant_id="t1", roles=["admin"]),
        authority_resolver=MockResolver(),
        namespace="default",
    )
    return SandboxRunner.for_script(ctx)


def test_a01_eval_basic_should_be_denied(runner):
    script = 'eval("from({model: \'X\'})")'
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_EVAL_DENIED, "A", "eval-denied"
    )


def test_a02_function_constructor_should_be_denied(runner):
    script = 'new Function("return from({model:\'X\'})")()'
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_EVAL_DENIED, "A", "eval-denied"
    )


def test_a03_async_fetch_should_be_denied(runner):
    script = "await fetch('http://evil.example/')"
    with pytest.raises(ComposeSandboxViolationError) as exc_info:
        runner.run(script)
    err = exc_info.value
    assert err.code in {LAYER_A_ASYNC_DENIED, LAYER_A_NETWORK_DENIED}
    assert err.layer == "A"


def test_a04_global_reflect_should_be_denied(runner):
    script = "Object.getPrototypeOf(from)"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_GLOBAL_DENIED, "A", "global-denied"
    )


def test_a05_date_now_should_be_denied(runner):
    script = "from({model:'X', slice:[{field:'t', op:'>', value: Date.now()}]})"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_TIME_DENIED, "A", "time-denied"
    )


def test_a06_security_param_injection_should_be_denied(runner):
    script = "dsl({model:'X', authorization:'Bearer hack'})"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_SECURITY_PARAM, "A", "security-param-denied"
    )


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "systemSlice",
        "deniedColumns",
        "fieldAccess",
        "dataSourceName",
        "routeModel",
        "namespace",
    ],
)
def test_a07_host_controlled_query_fields_should_be_denied(runner, forbidden_key):
    script = """
    dsl({model:'X', columns:['id'], %s: []});
    """ % forbidden_key
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_SECURITY_PARAM, "A", "security-param-denied"
    )


def test_a08_context_access_should_be_denied(runner):
    script = "const p = __context__.principal"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_CONTEXT_ACCESS, "A", "context-access-denied"
    )


def test_a09_module_import_should_be_denied(runner):
    script = "const fs = require('fs')"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_A_IO_DENIED, "A", "io-denied"
    )


def test_a10_legal_business_param_should_be_accepted():
    ctx = ComposeQueryContext(
        principal=Principal(user_id="u1", tenant_id="t1", roles=["admin"]),
        authority_resolver=MockResolver(),
        namespace="default",
        params={"orgId": "org001"},
    )
    legal_runner = SandboxRunner.for_script(ctx)
    script = "from({model:'X', columns:['id'], slice:[{field:'orgId', op:'=', value: params.orgId}]})"
    
    # We expect it to parse and build the plan without any Sandbox Violations
    legal_runner.run(script)
