"""Helper utilities for Compose Query Sandbox tests."""

from typing import Any, Callable

import pytest

from foggy.dataset_model.engine.compose.runtime import run_script
from foggy.dataset_model.engine.compose.sandbox import ComposeSandboxViolationError


def assert_sandbox_violation(
    callable_: Callable[[], Any],
    expected_code: str,
    expected_layer: str,
    expected_kind: str,
):
    with pytest.raises(ComposeSandboxViolationError) as exc_info:
        callable_()
    err = exc_info.value
    assert err.code == expected_code
    assert err.layer == expected_layer
    assert err.kind == expected_kind
    assert err.phase in {
        "script-parse",
        "script-eval",
        "plan-build",
        "schema-derive",
        "authority-resolve",
        "compile",
        "execute",
    }


class SandboxRunner:
    def __init__(self, ctx):
        self.ctx = ctx
        self.semantic_service = self._mock_semantic_service()

    def _mock_semantic_service(self):
        class MockBuildResult:
            def __init__(self, request):
                self.sql = "SELECT * FROM mock"
                self.params = []
                self.columns = [{"name": c} for c in request.columns]

        class MockService:
            def execute_sql(self, sql, params, *, route_model=None):
                pass
            def build_query_with_governance(self, model, request):
                return MockBuildResult(request)
        return MockService()

    @classmethod
    def for_script(cls, ctx):
        return cls(ctx)

    def run(self, script: str) -> Any:
        res = run_script(
            script,
            self.ctx,
            semantic_service=self.semantic_service,
            dialect="mysql",
        )
        return res.value

    def run_to_sql(self, script: str) -> str:
        res = run_script(
            script,
            self.ctx,
            semantic_service=self.semantic_service,
            dialect="mysql",
        )
        return res.sql or ""
