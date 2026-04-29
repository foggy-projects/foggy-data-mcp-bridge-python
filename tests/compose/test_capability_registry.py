"""v1.7 capability registry — descriptor, registry, policy, facade tests.

Covers P1.1-P1.4 acceptance criteria: descriptor validation, function
dispatch, object facade dispatch, policy deny, sandbox regression,
error sanitization, and default-surface-unchanged.
"""
from __future__ import annotations

import time
import pytest
from typing import Any

from foggy.dataset_model.engine.compose.capability import (
    CapabilityError,
    CapabilityInvalidDescriptorError,
    CapabilityMethodNotDeclaredError,
    CapabilityNotAllowedError,
    CapabilityNotRegisteredError,
    CapabilityPolicy,
    CapabilityRegistry,
    CapabilityReturnTypeDeniedError,
    CapabilitySideEffectDeniedError,
    CapabilityTimeoutError,
    CapabilityUnsupportedDialectError,
    FunctionDescriptor,
    MethodDescriptor,
    ObjectFacadeDescriptor,
    ObjectFacadeProxy,
    SqlFragment,
)
from foggy.dataset_model.engine.compose.capability.runtime_integration import (
    build_capability_context,
)


# ===================================================================
# Helpers
# ===================================================================

def _sql_scalar_desc(name="fiscal_month", dialects=None, allowed_in=None):
    return FunctionDescriptor(
        name=name,
        kind="sql_scalar",
        args_schema=[{"name": "date_value", "type": "date", "required": True}],
        return_type="string",
        deterministic=True,
        side_effect="none",
        allowed_in=allowed_in or ["formula", "compose_column"],
        dialects=dialects or ["postgres", "mysql"],
        audit_tag=f"test.{name}",
    )


def _pure_runtime_desc(name="normalize_region", allowed_in=None):
    return FunctionDescriptor(
        name=name,
        kind="pure_runtime",
        args_schema=[{"name": "value", "type": "string", "required": True}],
        return_type="string",
        deterministic=True,
        side_effect="none",
        allowed_in=allowed_in or ["compose_runtime"],
        audit_tag=f"test.{name}",
    )


def _method_desc(name="fiscal_year"):
    return MethodDescriptor(
        name=name,
        args_schema=[{"name": "date_value", "type": "date", "required": True}],
        return_type="int",
        side_effect="none",
        auth_scope="biz.calendar.read",
        timeout_ms=500,
        audit_tag=f"test.calendar.{name}",
    )


def _object_desc(name="calendar", methods=None):
    return ObjectFacadeDescriptor(
        object_name=name,
        methods=methods or [_method_desc()],
    )


class _CalendarFacade:
    def fiscal_year(self, date_value, start_month=1):
        return 2026

    def _private_method(self):
        return "secret"

    def undeclared_public(self):
        return "should not be callable"


def _dummy_renderer(args, dialect, bind):
    if dialect == "postgres":
        return SqlFragment(sql="to_char(%s, 'YYYY-MM')" % args["date_value"], params=[], return_type="string")
    if dialect == "mysql":
        return SqlFragment(sql="DATE_FORMAT(%s, '%%Y-%%m')" % args["date_value"], params=[], return_type="string")
    raise CapabilityUnsupportedDialectError(f"Unsupported dialect: {dialect}")


def _normalize_region(value: str) -> str:
    return {"cn-north": "north", "cn-east": "east"}.get(value, value)


# ===================================================================
# P1.1 — Descriptor Validation
# ===================================================================

class TestDescriptorValidation:

    def test_valid_function_descriptor(self):
        desc = _sql_scalar_desc()
        assert desc.name == "fiscal_month"
        assert desc.kind == "sql_scalar"

    def test_valid_pure_runtime_descriptor(self):
        desc = _pure_runtime_desc()
        assert desc.kind == "pure_runtime"

    def test_valid_method_descriptor(self):
        md = _method_desc()
        assert md.name == "fiscal_year"
        assert md.timeout_ms == 500

    def test_valid_object_descriptor(self):
        od = _object_desc()
        assert od.object_name == "calendar"
        assert len(od.methods) == 1

    def test_empty_name_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="must not be empty"):
            FunctionDescriptor(name="", kind="pure_runtime", args_schema=[], return_type="string",
                               deterministic=True, side_effect="none", allowed_in=["compose_runtime"],
                               audit_tag="test")

    def test_unsafe_name_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="unsafe characters"):
            _sql_scalar_desc(name="drop;table")

    def test_reserved_name_rejected(self):
        for reserved in ["from", "dsl", "Query", "params", "eval", "exec", "import"]:
            with pytest.raises(CapabilityInvalidDescriptorError, match="reserved"):
                _pure_runtime_desc(name=reserved)

    def test_dunder_name_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError):
            _pure_runtime_desc(name="__hidden")

    def test_invalid_kind_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="kind"):
            FunctionDescriptor(name="fn", kind="side_effect_fn", args_schema=[], return_type="string",
                               deterministic=True, side_effect="none", allowed_in=["compose_runtime"],
                               audit_tag="test")

    def test_side_effect_not_none_rejected(self):
        with pytest.raises(CapabilitySideEffectDeniedError, match="must be 'none'"):
            FunctionDescriptor(name="fn", kind="pure_runtime", args_schema=[], return_type="string",
                               deterministic=True, side_effect="write_db", allowed_in=["compose_runtime"],
                               audit_tag="test")

    def test_invalid_return_type_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="return_type"):
            FunctionDescriptor(name="fn", kind="pure_runtime", args_schema=[], return_type="Connection",
                               deterministic=True, side_effect="none", allowed_in=["compose_runtime"],
                               audit_tag="test")

    def test_sql_scalar_without_dialects_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="dialect"):
            FunctionDescriptor(name="fn", kind="sql_scalar", args_schema=[], return_type="string",
                               deterministic=True, side_effect="none", allowed_in=["formula"],
                               audit_tag="test")

    def test_empty_allowed_in_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="allowed_in"):
            FunctionDescriptor(name="fn", kind="pure_runtime", args_schema=[], return_type="string",
                               deterministic=True, side_effect="none", allowed_in=[],
                               audit_tag="test")

    def test_invalid_allowed_in_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="not recognized"):
            _pure_runtime_desc(allowed_in=["sql_injection_surface"])

    def test_empty_audit_tag_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="audit_tag"):
            FunctionDescriptor(name="fn", kind="pure_runtime", args_schema=[], return_type="string",
                               deterministic=True, side_effect="none", allowed_in=["compose_runtime"],
                               audit_tag="")

    def test_method_zero_timeout_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="timeout_ms"):
            MethodDescriptor(name="m", args_schema=[], return_type="int", side_effect="none",
                             auth_scope="scope", timeout_ms=0, audit_tag="test")

    def test_object_no_methods_rejected(self):
        with pytest.raises(CapabilityInvalidDescriptorError, match="at least one method"):
            ObjectFacadeDescriptor(object_name="empty", methods=[])

    def test_object_duplicate_method_rejected(self):
        m = _method_desc("dup")
        with pytest.raises(CapabilityInvalidDescriptorError, match="duplicate"):
            ObjectFacadeDescriptor(object_name="obj", methods=[m, m])


# ===================================================================
# P1.1 — Registry
# ===================================================================

class TestRegistry:

    def test_default_empty(self):
        reg = CapabilityRegistry()
        assert reg.is_empty()
        assert reg.function_names == frozenset()
        assert reg.object_names == frozenset()

    def test_register_sql_scalar(self):
        reg = CapabilityRegistry()
        reg.register_function(_sql_scalar_desc(), renderer=_dummy_renderer)
        assert reg.has_function("fiscal_month")

    def test_register_pure_runtime(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(), handler=_normalize_region)
        assert reg.has_function("normalize_region")

    def test_register_object_facade(self):
        reg = CapabilityRegistry()
        reg.register_object_facade(_object_desc(), target=_CalendarFacade())
        assert reg.has_object("calendar")

    def test_duplicate_function_rejected(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(), handler=_normalize_region)
        with pytest.raises(CapabilityInvalidDescriptorError, match="already registered"):
            reg.register_function(_pure_runtime_desc(), handler=_normalize_region)

    def test_duplicate_object_rejected(self):
        reg = CapabilityRegistry()
        reg.register_object_facade(_object_desc(), target=_CalendarFacade())
        with pytest.raises(CapabilityInvalidDescriptorError, match="already registered"):
            reg.register_object_facade(_object_desc(), target=_CalendarFacade())

    def test_name_collision_fn_obj(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(name="calendar"), handler=lambda v: v)
        with pytest.raises(CapabilityInvalidDescriptorError, match="already used"):
            reg.register_object_facade(
                ObjectFacadeDescriptor(object_name="calendar", methods=[_method_desc()]),
                target=_CalendarFacade(),
            )

    def test_sql_scalar_missing_renderer(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityInvalidDescriptorError, match="renderer"):
            reg.register_function(_sql_scalar_desc())

    def test_pure_runtime_missing_handler(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityInvalidDescriptorError, match="handler"):
            reg.register_function(_pure_runtime_desc())

    def test_object_method_not_on_target(self):
        class Empty:
            pass
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityInvalidDescriptorError, match="not found"):
            reg.register_object_facade(_object_desc(), target=Empty())

    def test_lookup_unregistered_function(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityNotRegisteredError, match="not registered"):
            reg.get_function("nonexistent")

    def test_lookup_unregistered_object(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityNotRegisteredError, match="not registered"):
            reg.get_object("nonexistent")


# ===================================================================
# P1.1 — Policy
# ===================================================================

class TestPolicy:

    def test_default_empty(self):
        p = CapabilityPolicy.empty()
        assert not p.is_function_allowed("any")
        assert not p.is_object_allowed("any")
        assert not p.is_scope_allowed("any")

    def test_function_allowed(self):
        p = CapabilityPolicy(allowed_functions=frozenset({"fn1"}))
        assert p.is_function_allowed("fn1")
        assert not p.is_function_allowed("fn2")

    def test_object_method_allowed(self):
        p = CapabilityPolicy(allowed_objects={"cal": frozenset({"fy"})})
        assert p.is_method_allowed("cal", "fy")
        assert not p.is_method_allowed("cal", "other")
        assert not p.is_method_allowed("other", "fy")

    def test_scope_allowed(self):
        p = CapabilityPolicy(allowed_scopes=frozenset({"biz.read"}))
        assert p.is_scope_allowed("biz.read")
        assert not p.is_scope_allowed("biz.write")


# ===================================================================
# P1.2 — SqlFragment
# ===================================================================

class TestSqlFragment:

    def test_basic(self):
        f = SqlFragment(sql="CASE WHEN ? THEN ? END", params=[1, 2], return_type="int")
        assert f.sql == "CASE WHEN ? THEN ? END"
        assert f.params == [1, 2]

    def test_invalid_sql_type(self):
        with pytest.raises(TypeError):
            SqlFragment(sql=123)

    def test_invalid_params_type(self):
        with pytest.raises(TypeError):
            SqlFragment(sql="x", params="not-a-list")


# ===================================================================
# P1.2 — Function Registry (sql_scalar renderer)
# ===================================================================

class TestSqlScalarFunction:

    def test_renderer_postgres(self):
        result = _dummy_renderer({"date_value": "t.order_date"}, "postgres", lambda v: v)
        assert isinstance(result, SqlFragment)
        assert "to_char" in result.sql

    def test_renderer_mysql(self):
        result = _dummy_renderer({"date_value": "t.order_date"}, "mysql", lambda v: v)
        assert isinstance(result, SqlFragment)
        assert "DATE_FORMAT" in result.sql

    def test_renderer_unsupported_dialect(self):
        with pytest.raises(CapabilityUnsupportedDialectError):
            _dummy_renderer({"date_value": "t.order_date"}, "oracle", lambda v: v)

    def test_bind_params_stable_order(self):
        f = SqlFragment(sql="? + ?", params=[1, 2])
        assert f.params == [1, 2]
        f2 = SqlFragment(sql="? + ?", params=[1, 2])
        assert f.params == f2.params


# ===================================================================
# P1.2 — Function Registry (pure_runtime)
# ===================================================================

class TestPureRuntimeFunction:

    def test_handler_call(self):
        assert _normalize_region("cn-north") == "north"
        assert _normalize_region("unknown") == "unknown"


# ===================================================================
# P1.2 / P1.3 — Runtime Integration
# ===================================================================

class TestRuntimeIntegration:

    def test_empty_registry_empty_context(self):
        ctx = build_capability_context(None, None)
        assert ctx == {}

    def test_empty_policy_empty_context(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(), handler=_normalize_region)
        ctx = build_capability_context(reg, None)
        assert ctx == {}

    def test_pure_runtime_injected_when_policy_allows(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(), handler=_normalize_region)
        policy = CapabilityPolicy(allowed_functions=frozenset({"normalize_region"}))
        ctx = build_capability_context(reg, policy)
        assert "normalize_region" in ctx
        assert callable(ctx["normalize_region"])
        assert ctx["normalize_region"]("cn-north") == "north"

    def test_pure_runtime_not_injected_when_policy_denies(self):
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(), handler=_normalize_region)
        policy = CapabilityPolicy.empty()
        ctx = build_capability_context(reg, policy)
        assert "normalize_region" not in ctx

    def test_sql_scalar_not_in_runtime_context(self):
        """sql_scalar functions live in the compilation layer, not runtime."""
        reg = CapabilityRegistry()
        reg.register_function(_sql_scalar_desc(), renderer=_dummy_renderer)
        policy = CapabilityPolicy(allowed_functions=frozenset({"fiscal_month"}))
        ctx = build_capability_context(reg, policy)
        assert "fiscal_month" not in ctx

    def test_object_facade_injected_as_proxy(self):
        reg = CapabilityRegistry()
        reg.register_object_facade(_object_desc(), target=_CalendarFacade())
        policy = CapabilityPolicy(
            allowed_objects={"calendar": frozenset({"fiscal_year"})},
            allowed_scopes=frozenset({"biz.calendar.read"}),
        )
        ctx = build_capability_context(reg, policy)
        assert "calendar" in ctx
        assert isinstance(ctx["calendar"], ObjectFacadeProxy)

    def test_object_facade_not_injected_when_policy_denies(self):
        reg = CapabilityRegistry()
        reg.register_object_facade(_object_desc(), target=_CalendarFacade())
        policy = CapabilityPolicy.empty()
        ctx = build_capability_context(reg, policy)
        assert "calendar" not in ctx

    def test_return_type_validation_on_pure_runtime(self):
        """pure_runtime returning unsafe type should raise."""
        class UnsafeObj:
            pass
        def bad_handler(v):
            return UnsafeObj()
        reg = CapabilityRegistry()
        reg.register_function(_pure_runtime_desc(name="bad_fn"), handler=bad_handler)
        policy = CapabilityPolicy(allowed_functions=frozenset({"bad_fn"}))
        ctx = build_capability_context(reg, policy)
        with pytest.raises(CapabilityReturnTypeDeniedError):
            ctx["bad_fn"]("x")


# ===================================================================
# P1.3 — Object Facade Proxy
# ===================================================================

class TestObjectFacadeProxy:

    def _make_proxy(self, policy=None):
        if policy is None:
            policy = CapabilityPolicy(
                allowed_objects={"calendar": frozenset({"fiscal_year"})},
                allowed_scopes=frozenset({"biz.calendar.read"}),
            )
        return ObjectFacadeProxy(
            descriptor=_object_desc(),
            target=_CalendarFacade(),
            policy=policy,
        )

    def test_declared_method_success(self):
        proxy = self._make_proxy()
        result = proxy.fiscal_year("2026-01-15")
        assert result == 2026

    def test_undeclared_method_denied(self):
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="not declared"):
            proxy.undeclared_public()

    def test_private_method_denied(self):
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            proxy._private_method()

    def test_dunder_dict_denied(self):
        """Accessing _target or _descriptor via attribute access is blocked."""
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            proxy._target
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            proxy._descriptor
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            proxy.__dict__

    def test_dunder_class_safe(self):
        """__class__ returns ObjectFacadeProxy, not the target class."""
        proxy = self._make_proxy()
        # __class__ is explicitly allowed in __getattribute__
        assert proxy.__class__ is ObjectFacadeProxy

    def test_dunder_globals_denied(self):
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            _ = proxy.__globals__

    def test_setattr_denied(self):
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            proxy.new_attr = "value"

    def test_delattr_denied(self):
        proxy = self._make_proxy()
        with pytest.raises(CapabilityMethodNotDeclaredError, match="denied"):
            del proxy.fiscal_year

    def test_auth_scope_denied(self):
        policy = CapabilityPolicy(
            allowed_objects={"calendar": frozenset({"fiscal_year"})},
            allowed_scopes=frozenset(),  # No scopes
        )
        proxy = self._make_proxy(policy=policy)
        with pytest.raises(CapabilityNotAllowedError, match="scope"):
            proxy.fiscal_year("2026-01-15")

    def test_policy_method_denied(self):
        policy = CapabilityPolicy(
            allowed_objects={"calendar": frozenset()},  # No methods allowed
            allowed_scopes=frozenset({"biz.calendar.read"}),
        )
        proxy = self._make_proxy(policy=policy)
        with pytest.raises(CapabilityNotAllowedError, match="not allowed"):
            proxy.fiscal_year("2026-01-15")

    def test_return_type_unsafe_denied(self):
        class UnsafeTarget:
            def fiscal_year(self, date_value, start_month=1):
                return object()  # Unsafe return
        proxy = ObjectFacadeProxy(
            descriptor=_object_desc(),
            target=UnsafeTarget(),
            policy=CapabilityPolicy(
                allowed_objects={"calendar": frozenset({"fiscal_year"})},
                allowed_scopes=frozenset({"biz.calendar.read"}),
            ),
        )
        with pytest.raises(CapabilityReturnTypeDeniedError, match="disallowed type"):
            proxy.fiscal_year("2026-01-15")

    def test_timeout_denied(self):
        class SlowTarget:
            def fiscal_year(self, date_value, start_month=1):
                time.sleep(2)
                return 2026
        short_timeout = MethodDescriptor(
            name="fiscal_year", args_schema=[], return_type="int",
            side_effect="none", auth_scope="biz.calendar.read",
            timeout_ms=50, audit_tag="test",
        )
        proxy = ObjectFacadeProxy(
            descriptor=ObjectFacadeDescriptor(object_name="calendar", methods=[short_timeout]),
            target=SlowTarget(),
            policy=CapabilityPolicy(
                allowed_objects={"calendar": frozenset({"fiscal_year"})},
                allowed_scopes=frozenset({"biz.calendar.read"}),
            ),
        )
        with pytest.raises(CapabilityTimeoutError, match="exceeded timeout"):
            proxy.fiscal_year("2026-01-15")

    def test_error_sanitization(self):
        """Errors from target should NOT leak internal details."""
        class ErrorTarget:
            def fiscal_year(self, date_value, start_month=1):
                raise RuntimeError("Internal DB connection to 192.168.1.1:5432 failed")
        proxy = ObjectFacadeProxy(
            descriptor=_object_desc(),
            target=ErrorTarget(),
            policy=CapabilityPolicy(
                allowed_objects={"calendar": frozenset({"fiscal_year"})},
                allowed_scopes=frozenset({"biz.calendar.read"}),
            ),
        )
        with pytest.raises(CapabilityMethodNotDeclaredError) as exc_info:
            proxy.fiscal_year("2026-01-15")
        # Must NOT leak the internal IP / port.
        assert "192.168.1.1" not in str(exc_info.value)
        assert "5432" not in str(exc_info.value)

    def test_dir_only_shows_declared_methods(self):
        proxy = self._make_proxy()
        visible = dir(proxy)
        assert "fiscal_year" in visible
        assert "_private_method" not in visible
        assert "undeclared_public" not in visible

    def test_repr_safe(self):
        proxy = self._make_proxy()
        r = repr(proxy)
        assert "ObjectFacadeProxy" in r
        assert "calendar" in r


# ===================================================================
# P1.4 — Default Surface Unchanged
# ===================================================================

class TestDefaultSurfaceUnchanged:

    def test_no_registry_no_policy_no_injection(self):
        ctx = build_capability_context(None, None)
        assert ctx == {}

    def test_empty_registry_empty_policy_no_injection(self):
        ctx = build_capability_context(CapabilityRegistry(), CapabilityPolicy.empty())
        assert ctx == {}


# ===================================================================
# P1.4 — Error Code Coverage
# ===================================================================

class TestErrorCodes:

    def test_all_error_codes_are_strings(self):
        from foggy.dataset_model.engine.compose.capability.errors import ALL_CAPABILITY_CODES
        for code in ALL_CAPABILITY_CODES:
            assert isinstance(code, str)
            assert code.startswith("capability/")

    def test_invalid_error_code_raises(self):
        with pytest.raises(ValueError, match="ALL_CAPABILITY_CODES"):
            CapabilityError("invalid/code", "msg")

    def test_error_hierarchy(self):
        assert issubclass(CapabilityNotRegisteredError, CapabilityError)
        assert issubclass(CapabilityNotAllowedError, CapabilityError)
        assert issubclass(CapabilityInvalidDescriptorError, CapabilityError)
        assert issubclass(CapabilityUnsupportedDialectError, CapabilityError)
        assert issubclass(CapabilityMethodNotDeclaredError, CapabilityError)
        assert issubclass(CapabilitySideEffectDeniedError, CapabilityError)
        assert issubclass(CapabilityReturnTypeDeniedError, CapabilityError)
        assert issubclass(CapabilityTimeoutError, CapabilityError)
