"""Formula Compiler + Capability Registry integration tests.

Verifies P1.5 acceptance criteria: sql_scalar functions generate
parameterized SQL, fail-closed for unregistered / denied / unsupported
functions, and default surface remains unchanged.
"""
from __future__ import annotations

import pytest

from foggy.dataset_model.semantic.formula_compiler import (
    FormulaCompiler,
    FormulaFunctionNotAllowedError,
    FormulaSyntaxError,
)
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from foggy.dataset_model.engine.compose.capability import (
    CapabilityPolicy,
    CapabilityRegistry,
    FunctionDescriptor,
    SqlFragment,
)


def _fiscal_month_renderer(args, dialect, bind):
    if dialect == "mysql":
        return SqlFragment(
            sql=f"DATE_FORMAT({args['date']}, '%Y-%m')",
            params=[],
        )
    return SqlFragment(sql="UNSUPPORTED", params=[])


def _concat_renderer(args, dialect, bind):
    if dialect == "mysql":
        return SqlFragment(
            sql=f"CONCAT({args['a']}, {args['b']})",
            params=[],
        )
    return SqlFragment(sql="UNSUPPORTED", params=[])


@pytest.fixture
def registry():
    reg = CapabilityRegistry()
    reg.register_function(
        FunctionDescriptor(
            name="fiscal_month",
            kind="sql_scalar",
            args_schema=[{"name": "date", "type": "date", "required": True}],
            return_type="string",
            deterministic=True,
            side_effect="none",
            allowed_in=["formula", "compose_column"],
            dialects=["mysql"],
            audit_tag="test.fiscal_month",
        ),
        renderer=_fiscal_month_renderer,
    )
    reg.register_function(
        FunctionDescriptor(
            name="concat_str",
            kind="sql_scalar",
            args_schema=[
                {"name": "a", "type": "string", "required": True},
                {"name": "b", "type": "string", "required": True},
            ],
            return_type="string",
            deterministic=True,
            side_effect="none",
            allowed_in=["formula", "compose_column"],
            dialects=["mysql"],
            audit_tag="test.concat_str",
        ),
        renderer=_concat_renderer,
    )
    # A function not allowed in formula
    reg.register_function(
        FunctionDescriptor(
            name="system_call",
            kind="sql_scalar",
            args_schema=[],
            return_type="string",
            deterministic=False,
            side_effect="none",
            allowed_in=["compose_runtime"],
            dialects=["mysql"],
            audit_tag="test.system",
        ),
        renderer=lambda args, d, b: SqlFragment(sql="1", params=[]),
    )
    return reg


@pytest.fixture
def policy():
    return CapabilityPolicy(
        allowed_functions=frozenset({"fiscal_month", "concat_str", "system_call"})
    )


def test_compiler_with_registry_success(registry, policy):
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    # Using registered functions
    res = compiler.compile("fiscal_month(created_at)", lambda n: f"t.{n}")
    assert res.sql_fragment == "DATE_FORMAT(t.created_at, '%Y-%m')"

    res2 = compiler.compile("concat_str('A', 'B')", lambda n: f"t.{n}")
    assert res2.sql_fragment == "CONCAT(?, ?)"
    assert res2.bind_params == ("A", "B")


def test_compiler_unregistered_function(registry, policy):
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaFunctionNotAllowedError):
        compiler.compile("unregistered_fn(x)", lambda n: f"t.{n}")


def test_compiler_policy_deny(registry):
    # Only allow concat_str, deny fiscal_month
    policy = CapabilityPolicy(allowed_functions=frozenset({"concat_str"}))
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaFunctionNotAllowedError, match="not allowed by the current policy"):
        compiler.compile("fiscal_month(x)", lambda n: f"t.{n}")


def test_compiler_surface_deny(registry, policy):
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaFunctionNotAllowedError, match="not allowed in formula/compose_column"):
        compiler.compile("system_call()", lambda n: "")


def test_compiler_invalid_arg_count(registry, policy):
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaSyntaxError, match="expects 1 arguments, got 2"):
        compiler.compile("fiscal_month(x, y)", lambda n: f"t.{n}")


def test_compiler_unsupported_dialect(registry, policy):
    compiler = FormulaCompiler(
        SqlDialect.of("postgres"),  # postgres is not in dialects list
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaFunctionNotAllowedError, match="does not support dialect 'postgres'"):
        compiler.compile("fiscal_month(x)", lambda n: f"t.{n}")


def test_compiler_invalid_renderer_return(registry, policy):
    # Register a function with bad renderer
    registry.register_function(
        FunctionDescriptor(
            name="bad_fn",
            kind="sql_scalar",
            args_schema=[],
            return_type="string",
            deterministic=True,
            side_effect="none",
            allowed_in=["formula"],
            dialects=["mysql"],
            audit_tag="test.bad",
        ),
        renderer=lambda args, d, b: "RAW STRING (NOT SqlFragment)",
    )
    policy = CapabilityPolicy(
        allowed_functions=frozenset({"bad_fn"})
    )
    compiler = FormulaCompiler(
        SqlDialect.of("mysql"),
        capability_registry=registry,
        capability_policy=policy,
    )
    with pytest.raises(FormulaSyntaxError, match="did not return a SqlFragment"):
        compiler.compile("bad_fn()", lambda n: "")


def test_compiler_default_surface_unchanged():
    # Registry is None by default
    compiler = FormulaCompiler(SqlDialect.of("mysql"))
    # Standard functions work
    res = compiler.compile("if(a>0, 1, 0)", lambda n: f"t.{n}")
    assert "CASE WHEN" in res.sql_fragment
    
    # Custom functions fail
    with pytest.raises(FormulaFunctionNotAllowedError):
        compiler.compile("fiscal_month(x)", lambda n: f"t.{n}")
