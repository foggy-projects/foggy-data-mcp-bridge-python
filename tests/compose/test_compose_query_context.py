"""M1 ComposeQueryContext invariants — cross-repo parity test."""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.context import (
    ComposeQueryContext,
    Principal,
)


class _StubResolver:
    """Minimal object satisfying the AuthorityResolver duck-type check."""

    def resolve(self, request):  # noqa: D401
        raise NotImplementedError


class _NotAResolver:
    """Intentionally missing a ``resolve`` method."""


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id="u001", tenant_id="t001", roles=["admin"])


@pytest.fixture
def resolver() -> _StubResolver:
    return _StubResolver()


class TestComposeQueryContextConstruction:
    def test_minimal_valid_construction(self, principal, resolver):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
        )
        assert ctx.principal is principal
        assert ctx.namespace == "odoo"
        assert ctx.authority_resolver is resolver
        assert ctx.trace_id is None
        assert ctx.params is None
        assert ctx.extensions is None

    def test_principal_required_type_checked(self, resolver):
        with pytest.raises(TypeError):
            ComposeQueryContext(
                principal="u001",  # type: ignore[arg-type]
                namespace="odoo",
                authority_resolver=resolver,
            )

    def test_namespace_required_non_blank(self, principal, resolver):
        with pytest.raises(ValueError):
            ComposeQueryContext(
                principal=principal,
                namespace="",
                authority_resolver=resolver,
            )
        with pytest.raises(ValueError):
            ComposeQueryContext(
                principal=principal,
                namespace=None,  # type: ignore[arg-type]
                authority_resolver=resolver,
            )

    def test_authority_resolver_required(self, principal):
        with pytest.raises(ValueError):
            ComposeQueryContext(
                principal=principal,
                namespace="odoo",
                authority_resolver=None,
            )

    def test_authority_resolver_ducktype_checked(self, principal):
        """Any object lacking a callable .resolve method is rejected."""
        with pytest.raises(TypeError):
            ComposeQueryContext(
                principal=principal,
                namespace="odoo",
                authority_resolver=_NotAResolver(),
            )


class TestComposeQueryContextParams:
    def test_params_frozen_after_construction(self, principal, resolver):
        src = {"orgId": "org001"}
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
            params=src,
        )

        # The context holds a read-only view; the caller's original dict must
        # not be reflected into mutations either direction.
        src["orgId"] = "org002"
        assert ctx.params["orgId"] == "org001", (
            "ComposeQueryContext.params must snapshot the source mapping"
        )

        with pytest.raises(Exception):  # MappingProxyType is read-only
            ctx.params["orgId"] = "org003"  # type: ignore[index]

    def test_param_accessor_returns_default_when_params_none(
        self, principal, resolver
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
        )
        assert ctx.param("orgId") is None
        assert ctx.param("orgId", default="fallback") == "fallback"

    def test_param_accessor_reads_from_snapshot(self, principal, resolver):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
            params={"orgId": "org001", "deptId": "d1"},
        )
        assert ctx.param("orgId") == "org001"
        assert ctx.param("missing", default="x") == "x"


class TestComposeQueryContextImmutability:
    def test_frozen_dataclass_rejects_attribute_mutation(self, principal, resolver):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
        )
        with pytest.raises(Exception):
            ctx.namespace = "other"  # type: ignore[misc]
