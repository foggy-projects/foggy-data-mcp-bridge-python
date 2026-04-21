"""M1 AuthorityResolver Protocol — fake-resolver contract sanity tests.

This file does NOT test a real resolver; it verifies the Protocol surface
works under common patterns hosts will use (duck-type conformance,
runtime_checkable isinstance, fail-closed exception propagation).
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.context import Principal
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    AuthorityResolutionError,
    AuthorityResolver,
    ModelBinding,
    ModelQuery,
    error_codes,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class EchoResolver:
    """Good-citizen resolver: returns empty ModelBinding for each model."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        return AuthorityResolution(
            bindings={mq.model: ModelBinding() for mq in request.models},
        )


class PartialResolver:
    """Returns bindings for only the first model — contract violation."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        first = request.models[0]
        return AuthorityResolution(bindings={first.model: ModelBinding()})


class RaisingResolver:
    """Always raises AuthorityResolutionError."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        raise AuthorityResolutionError(
            code=error_codes.UPSTREAM_FAILURE,
            message="upstream offline",
            model_involved=request.models[0].model,
        )


class NotAResolver:
    """Lacks a resolve method."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id="u001", tenant_id="t001", roles=["admin"])


@pytest.fixture
def multi_model_request(principal) -> AuthorityRequest:
    return AuthorityRequest(
        principal=principal,
        namespace="odoo",
        models=[
            ModelQuery(model="SaleOrderQM", tables=["sale_order"]),
            ModelQuery(model="CrmLeadQM", tables=["crm_lead"]),
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtocolRuntimeCheck:
    def test_runtime_isinstance_accepts_duck_typed_resolver(self):
        """@runtime_checkable Protocol + any .resolve method ⇒ isinstance True."""
        assert isinstance(EchoResolver(), AuthorityResolver)

    def test_runtime_isinstance_rejects_missing_method(self):
        assert not isinstance(NotAResolver(), AuthorityResolver)


class TestEchoResolverSatisfiesFullContract:
    def test_bindings_key_set_equals_request_model_set(self, multi_model_request):
        """EchoResolver's output passes the key-set invariant."""
        resolution = EchoResolver().resolve(multi_model_request)
        assert set(resolution.bindings.keys()) == set(
            multi_model_request.model_names()
        )

    def test_each_binding_has_default_empty_collections(self, multi_model_request):
        resolution = EchoResolver().resolve(multi_model_request)
        for name, binding in resolution.bindings.items():
            assert binding.field_access is None
            assert binding.denied_columns == []
            assert binding.system_slice == []


class TestPartialResolverViolatesContract:
    """A caller (not the Protocol itself) is expected to detect this; the
    fake here exists so downstream guard code has a convenient negative
    case to exercise."""

    def test_partial_response_is_detectable_by_key_set_check(
        self, multi_model_request
    ):
        resolution = PartialResolver().resolve(multi_model_request)
        expected = set(multi_model_request.model_names())
        actual = set(resolution.bindings.keys())
        missing = expected - actual
        assert missing == {"CrmLeadQM"}, (
            "PartialResolver must leave the second model unbound so callers "
            "can raise MODEL_BINDING_MISSING"
        )


class TestRaisingResolverPropagatesFailClosed:
    def test_resolver_exception_propagates(self, multi_model_request):
        resolver = RaisingResolver()
        with pytest.raises(AuthorityResolutionError) as exc_info:
            resolver.resolve(multi_model_request)
        err = exc_info.value
        assert err.code == error_codes.UPSTREAM_FAILURE
        assert err.model_involved == "SaleOrderQM"
        assert err.phase == error_codes.PHASE_AUTHORITY_RESOLVE


class TestContextIntegration:
    """Pattern test: a ComposeQueryContext accepts any Protocol-compatible
    resolver without requiring explicit subclassing."""

    def test_compose_context_accepts_duck_typed_resolver(self, principal):
        from foggy.dataset_model.engine.compose.context import ComposeQueryContext

        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=EchoResolver(),
        )
        assert isinstance(ctx.authority_resolver, AuthorityResolver)
