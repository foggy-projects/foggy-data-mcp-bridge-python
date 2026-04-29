"""v1.8 controlled fsscript library import tests."""

from __future__ import annotations

import hashlib
from typing import List

import pytest

from foggy.dataset_model.engine.compose.capability import (
    CapabilityImportCycleError,
    CapabilityImportNotAllowedError,
    CapabilityInvalidDescriptorError,
    CapabilityNotRegisteredError,
    CapabilityPolicy,
    CapabilityRegistry,
    CapabilitySymbolCollisionError,
    CapabilitySymbolNotDeclaredError,
    LibraryDescriptor,
)
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.runtime import run_script
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)
from foggy.dataset_model.engine.compose.sandbox.exceptions import (
    ComposeSandboxViolationError,
)


class _StubResolver:
    def resolve(self, request):
        return AuthorityResolution(bindings={
            mq.model: ModelBinding() for mq in request.models
        })


class _StubSemanticService:
    execute_calls: List = []

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        return [{"id": 1}]


def _ctx():
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=_StubResolver(),
    )


def _sha(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _descriptor(
    name: str,
    source: str,
    *,
    exports: list[str],
    dependencies: list[str] | None = None,
    allowed_in: list[str] | None = None,
) -> LibraryDescriptor:
    return LibraryDescriptor(
        name=name,
        version="1.0.0",
        source_hash=_sha(source),
        exports=exports,
        dependencies=dependencies or [],
        allowed_in=allowed_in or ["compose_runtime"],
        audit_tag=f"test:{name}",
    )


def _registry_with_library(
    name: str,
    source: str,
    *,
    exports: list[str],
    dependencies: list[str] | None = None,
) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register_library(
        _descriptor(
            name,
            source,
            exports=exports,
            dependencies=dependencies,
        ),
        source=source,
    )
    return registry


def test_library_descriptor_rejects_path_like_name():
    with pytest.raises(CapabilityInvalidDescriptorError):
        _descriptor("../shared.fsscript", "export const x = 1;", exports=["x"])


def test_library_registry_rejects_source_hash_mismatch():
    registry = CapabilityRegistry()
    descriptor = LibraryDescriptor(
        name="biz.math",
        version="1.0.0",
        source_hash=_sha("export const x = 1;"),
        exports=["x"],
        allowed_in=["compose_runtime"],
        audit_tag="test:hash",
    )

    with pytest.raises(CapabilityInvalidDescriptorError):
        registry.register_library(descriptor, source="export const x = 2;")


def test_library_descriptor_rejects_duplicate_exports():
    with pytest.raises(CapabilityInvalidDescriptorError):
        _descriptor(
            "biz.dup",
            "export const x = 1;",
            exports=["x", "x"],
        )


def test_default_compose_surface_still_denies_import():
    with pytest.raises(ComposeSandboxViolationError):
        run_script(
            "import { add } from 'biz.math'; return add(1, 2);",
            _ctx(),
            semantic_service=_StubSemanticService(),
        )


def test_controlled_library_import_success():
    source = "export function add(a, b) { return a + b; }"
    registry = _registry_with_library("biz.math", source, exports=["add"])
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.math"}))

    result = run_script(
        "import { add } from 'biz.math'; return add(2, 3);",
        _ctx(),
        semantic_service=_StubSemanticService(),
        library_registry=registry,
        library_policy=policy,
    )

    assert result.value == 5


def test_controlled_library_import_unregistered_fails_closed():
    registry = CapabilityRegistry()
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.missing"}))

    with pytest.raises(CapabilityNotRegisteredError):
        run_script(
            "import { helper } from 'biz.missing'; return helper();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_controlled_library_import_policy_deny():
    source = "export function helper() { return 1; }"
    registry = _registry_with_library("biz.helper", source, exports=["helper"])
    policy = CapabilityPolicy.empty()

    with pytest.raises(CapabilityImportNotAllowedError):
        run_script(
            "import { helper } from 'biz.helper'; return helper();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_controlled_library_import_symbol_deny():
    source = (
        "export function visible() { return 1; } "
        "export function hidden() { return 2; }"
    )
    registry = _registry_with_library(
        "biz.helper",
        source,
        exports=["visible", "hidden"],
    )
    policy = CapabilityPolicy(
        allowed_libraries=frozenset({"biz.helper"}),
        allowed_symbols={"biz.helper": frozenset({"visible"})},
    )

    with pytest.raises(CapabilityImportNotAllowedError):
        run_script(
            "import { hidden } from 'biz.helper'; return hidden();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_controlled_library_import_undeclared_symbol():
    source = "export function helper() { return 1; }"
    registry = _registry_with_library("biz.helper", source, exports=["helper"])
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.helper"}))

    with pytest.raises(CapabilitySymbolNotDeclaredError):
        run_script(
            "import { missing } from 'biz.helper'; return missing();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_controlled_library_import_path_traversal_denied_by_scanner():
    source = "export function helper() { return 1; }"
    registry = _registry_with_library("biz.helper", source, exports=["helper"])
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.helper"}))

    with pytest.raises(ComposeSandboxViolationError):
        run_script(
            "import { helper } from '../helper.fsscript'; return helper();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_dynamic_import_denied_by_scanner():
    registry = CapabilityRegistry()
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.helper"}))

    with pytest.raises(ComposeSandboxViolationError):
        run_script(
            "const x = import('biz.helper'); return x;",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_import_binding_collision_fails_closed():
    source = "export function helper() { return 1; }"
    registry = _registry_with_library("biz.helper", source, exports=["helper"])
    policy = CapabilityPolicy(allowed_libraries=frozenset({"biz.helper"}))

    with pytest.raises(CapabilitySymbolCollisionError):
        run_script(
            "import { helper as params } from 'biz.helper'; return params();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )


def test_declared_dependency_import_success():
    math_source = "export function add(a, b) { return a + b; }"
    calc_source = (
        "import { add } from 'biz.math'; "
        "export function double(x) { return add(x, x); }"
    )
    registry = CapabilityRegistry()
    registry.register_library(
        _descriptor("biz.math", math_source, exports=["add"]),
        source=math_source,
    )
    registry.register_library(
        _descriptor(
            "biz.calc",
            calc_source,
            exports=["double"],
            dependencies=["biz.math"],
        ),
        source=calc_source,
    )
    policy = CapabilityPolicy(
        allowed_libraries=frozenset({"biz.math", "biz.calc"}),
    )

    result = run_script(
        "import { double } from 'biz.calc'; return double(4);",
        _ctx(),
        semantic_service=_StubSemanticService(),
        library_registry=registry,
        library_policy=policy,
    )

    assert result.value == 8


def test_library_import_cycle_fails_closed():
    a_source = "import { b } from 'biz.b'; export function a() { return b(); }"
    b_source = "import { a } from 'biz.a'; export function b() { return a(); }"
    registry = CapabilityRegistry()
    registry.register_library(
        _descriptor("biz.a", a_source, exports=["a"], dependencies=["biz.b"]),
        source=a_source,
    )
    registry.register_library(
        _descriptor("biz.b", b_source, exports=["b"], dependencies=["biz.a"]),
        source=b_source,
    )
    policy = CapabilityPolicy(
        allowed_libraries=frozenset({"biz.a", "biz.b"}),
    )

    with pytest.raises(CapabilityImportCycleError):
        run_script(
            "import { a } from 'biz.a'; return a();",
            _ctx(),
            semantic_service=_StubSemanticService(),
            library_registry=registry,
            library_policy=policy,
        )
