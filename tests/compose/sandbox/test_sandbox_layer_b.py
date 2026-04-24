"""Layer B sandbox tests (DSL expressions)."""

import pytest

from foggy.dataset_model.engine.compose.context import ComposeQueryContext, Principal
from foggy.dataset_model.engine.compose.sandbox.error_codes import (
    LAYER_B_DERIVED_FN_DENIED,
    LAYER_B_FUNCTION_DENIED,
    LAYER_B_INJECTION_SUSPECTED,
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


def test_b01_hex_function_should_be_denied(runner):
    script = "from({model:'X', columns: ['CHAR(0x41) as x']})"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_B_FUNCTION_DENIED, "B", "function-denied"
    )


def test_b02_blocked_function_sleep_should_be_denied(runner):
    script = "from({model:'X', columns: ['SLEEP(5) as x']})"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_B_FUNCTION_DENIED, "B", "function-denied"
    )


def test_b03_union_select_injection_should_be_neutralized(runner):
    script = "from({model:'X', slice:[{field:'name', op:'=', value:\"a' UNION SELECT 1,2,3--\"}]})"
    try:
        sql = runner.run_to_sql(script)
        assert "UNION SELECT" not in sql, f"Raw injection payload leaked into SQL: {sql}"
    except ComposeSandboxViolationError as ex:
        assert ex.code == LAYER_B_INJECTION_SUSPECTED


def test_b04_derived_raw_sql_should_be_denied(runner):
    script = """
    const base = from({model:'X', columns:['id']});
    base.query({columns:['RAW_SQL("DROP TABLE x")']});
    """
    with pytest.raises(ComposeSandboxViolationError) as exc_info:
        runner.run(script)
    err = exc_info.value
    assert err.code in {LAYER_B_DERIVED_FN_DENIED, LAYER_B_FUNCTION_DENIED}
    assert err.layer == "B"


def test_b05_allowed_date_diff(runner):
    script = "from({model:'X', columns: ['DATE_DIFF(create_date, write_date) as days']})"
    runner.run(script)


def test_b06_allowed_iif_sum(runner):
    script = "from({model:'X', columns: ['SUM(IIF(state == 1, 1, 0)) as openCount'], groupBy: ['id']})"
    runner.run(script)


def test_b07_blocked_load_file(runner):
    script = "from({model:'X', columns: ['LOAD_FILE(\"/etc/passwd\") as x']})"
    assert_sandbox_violation(
        lambda: runner.run(script), LAYER_B_FUNCTION_DENIED, "B", "function-denied"
    )
