"""M5 ``resolve_authority_for_plan`` — top-level batch resolution pipeline.

Covers:
    * Single-model round trip (Echo resolver)
    * Multi-model round trip with dedup across duplicated references
    * Request-level dedup: one resolver call per batch, not per reference
    * ModelInfoProvider injection (tables propagated into ModelQuery)
    * NullModelInfoProvider fallback (tables == [])
    * Fail-closed branches:
        - RESOLVER_NOT_AVAILABLE when context has no resolver
        - UPSTREAM_FAILURE when resolver raises non-AuthorityResolutionError
        - AuthorityResolutionError propagates verbatim (no wrapping)
        - INVALID_RESPONSE on non-AuthorityResolution return
        - INVALID_RESPONSE on wrong-typed binding value
        - INVALID_RESPONSE on extra keys
        - MODEL_BINDING_MISSING (first absent in request order)
"""

from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from foggy.dataset_model.engine.compose.authority import (
    ModelInfoProvider,
    NullModelInfoProvider,
    resolve_authority_for_plan,
)
from foggy.dataset_model.engine.compose.context import (
    ComposeQueryContext,
    Principal,
)
from foggy.dataset_model.engine.compose.plan import BaseModelPlan, from_
from foggy.dataset_model.engine.compose.plan.plan import JoinOn
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    AuthorityResolutionError,
    ModelBinding,
    error_codes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id="u001", tenant_id="t001", roles=["analyst"])


@pytest.fixture
def sale_order() -> BaseModelPlan:
    return from_(model="SaleOrderQM", columns=["id", "amount"])


@pytest.fixture
def crm_lead() -> BaseModelPlan:
    return from_(model="CrmLeadQM", columns=["id"])


@pytest.fixture
def partner() -> BaseModelPlan:
    return from_(model="ResPartnerQM", columns=["id", "name"])


# ---------------------------------------------------------------------------
# Test resolver fakes
# ---------------------------------------------------------------------------


class EchoResolver:
    """Returns an empty ModelBinding for each requested model. Counts calls."""

    def __init__(self) -> None:
        self.calls: List[AuthorityRequest] = []

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        self.calls.append(request)
        return AuthorityResolution(
            bindings={mq.model: ModelBinding() for mq in request.models}
        )


class StaticTableProvider:
    """Returns a fixed table list per model — simulates a real JoinGraph lookup."""

    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping

    def get_tables_for_model(
        self, model_name: str, namespace: str
    ) -> Optional[List[str]]:
        return self._mapping.get(model_name)


class NoneReturningProvider:
    """Provider that returns ``None`` (model unknown). Tables should coerce to []."""

    def get_tables_for_model(
        self, model_name: str, namespace: str
    ) -> Optional[List[str]]:
        return None


class RaisingResolver:
    """Raises AuthorityResolutionError — propagation test."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        raise AuthorityResolutionError(
            code=error_codes.IR_RULE_UNMAPPED_FIELD,
            message="ir.rule references unmapped QM field",
            model_involved=request.models[0].model,
        )


class BoomResolver:
    """Raises a plain Exception — must surface as UPSTREAM_FAILURE."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        raise RuntimeError("kaboom")


class NonAuthorityResponseResolver:
    """Returns something that isn't an AuthorityResolution — INVALID_RESPONSE."""

    def resolve(self, request: AuthorityRequest) -> Any:
        return {"not": "a resolution"}


class ExtraKeyResolver:
    """Returns a binding set with extra keys — INVALID_RESPONSE."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        bindings = {mq.model: ModelBinding() for mq in request.models}
        bindings["PhantomModel"] = ModelBinding()
        return AuthorityResolution(bindings=bindings)


class MissingKeyResolver:
    """Returns a binding set that omits the second model — MODEL_BINDING_MISSING."""

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        first = request.models[0]
        return AuthorityResolution(bindings={first.model: ModelBinding()})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSingleModel:
    def test_single_model_round_trip(self, principal, sale_order):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
        )
        bindings = resolve_authority_for_plan(sale_order, ctx)
        assert set(bindings.keys()) == {"SaleOrderQM"}
        assert isinstance(bindings["SaleOrderQM"], ModelBinding)
        # Default ModelBinding has no field_access restriction.
        assert bindings["SaleOrderQM"].field_access is None

    def test_calls_resolver_exactly_once(self, principal, sale_order):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        resolve_authority_for_plan(sale_order, ctx)
        assert len(resolver.calls) == 1

    def test_request_carries_principal_and_namespace(
        self, principal, sale_order
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        resolve_authority_for_plan(sale_order, ctx)
        req = resolver.calls[0]
        assert req.principal is principal
        assert req.namespace == "odoo"

    def test_request_carries_trace_id_when_set(self, principal, sale_order):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=resolver,
            trace_id="trace-xyz",
        )
        resolve_authority_for_plan(sale_order, ctx)
        assert resolver.calls[0].trace_id == "trace-xyz"


# ---------------------------------------------------------------------------
# Multi-model + dedup
# ---------------------------------------------------------------------------


class TestMultiModel:
    def test_join_produces_two_bindings(
        self, principal, sale_order, partner
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        joined = sale_order.join(
            partner,
            type="left",
            on=[JoinOn(left="partner_id", op="=", right="id")],
        )
        bindings = resolve_authority_for_plan(joined, ctx)
        assert set(bindings.keys()) == {"SaleOrderQM", "ResPartnerQM"}

    def test_request_preserves_left_right_order(
        self, principal, sale_order, partner
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        joined = sale_order.join(
            partner,
            type="left",
            on=[JoinOn(left="partner_id", op="=", right="id")],
        )
        resolve_authority_for_plan(joined, ctx)
        assert resolver.calls[0].model_names() == [
            "SaleOrderQM",
            "ResPartnerQM",
        ]

    def test_duplicate_references_deduped_in_request(
        self, principal, sale_order
    ):
        """Same QM in two arms of a union → one request entry, one binding."""
        sale_other = from_(model="SaleOrderQM", columns=["id"])
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        union = sale_order.union(sale_other)
        bindings = resolve_authority_for_plan(union, ctx)
        assert list(bindings.keys()) == ["SaleOrderQM"]
        assert len(resolver.calls) == 1
        assert resolver.calls[0].model_names() == ["SaleOrderQM"]


# ---------------------------------------------------------------------------
# ModelInfoProvider integration
# ---------------------------------------------------------------------------


class TestModelInfoProvider:
    def test_custom_provider_forwards_tables(self, principal, sale_order):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        provider = StaticTableProvider(
            {"SaleOrderQM": ["sale_order", "sale_order_line"]}
        )
        resolve_authority_for_plan(
            sale_order, ctx, model_info_provider=provider
        )
        mq = resolver.calls[0].models[0]
        assert mq.tables == ["sale_order", "sale_order_line"]

    def test_provider_returning_none_coerced_to_empty_list(
        self, principal, sale_order
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        resolve_authority_for_plan(
            sale_order, ctx, model_info_provider=NoneReturningProvider()
        )
        mq = resolver.calls[0].models[0]
        assert mq.tables == []

    def test_null_provider_fallback_gives_empty_tables(
        self, principal, sale_order
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        # Explicitly pass NullModelInfoProvider to exercise the path.
        resolve_authority_for_plan(
            sale_order, ctx, model_info_provider=NullModelInfoProvider()
        )
        mq = resolver.calls[0].models[0]
        assert mq.tables == []

    def test_default_provider_is_null_provider(
        self, principal, sale_order
    ):
        resolver = EchoResolver()
        ctx = ComposeQueryContext(
            principal=principal, namespace="odoo", authority_resolver=resolver
        )
        resolve_authority_for_plan(sale_order, ctx)  # no provider kwarg
        mq = resolver.calls[0].models[0]
        assert mq.tables == []

    def test_provider_protocol_isinstance_on_null(self):
        assert isinstance(NullModelInfoProvider(), ModelInfoProvider)


# ---------------------------------------------------------------------------
# Fail-closed branches
# ---------------------------------------------------------------------------


class TestFailClosedNoResolver:
    def test_none_context_raises_resolver_not_available(self, sale_order):
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, None)
        assert exc.value.code == error_codes.RESOLVER_NOT_AVAILABLE

    def test_context_with_null_resolver_raises_resolver_not_available(
        self, principal, sale_order
    ):
        # ComposeQueryContext rejects null resolver, so we build a
        # MagicMock-backed surrogate that passes ctor but whose
        # ``authority_resolver`` is None at the time of the call.
        fake_ctx = MagicMock(spec=["principal", "namespace", "authority_resolver", "trace_id"])
        fake_ctx.principal = principal
        fake_ctx.namespace = "odoo"
        fake_ctx.authority_resolver = None
        fake_ctx.trace_id = None
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, fake_ctx)
        assert exc.value.code == error_codes.RESOLVER_NOT_AVAILABLE


class TestFailClosedResolverRaises:
    def test_authority_error_propagates_verbatim(self, principal, sale_order):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=RaisingResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        # Code preserved from the resolver — not rewritten to UPSTREAM_FAILURE.
        assert exc.value.code == error_codes.IR_RULE_UNMAPPED_FIELD

    def test_plain_exception_wrapped_as_upstream_failure(
        self, principal, sale_order
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=BoomResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        assert exc.value.code == error_codes.UPSTREAM_FAILURE
        # Cause chain preserved.
        assert isinstance(exc.value.__cause__, RuntimeError)
        assert str(exc.value.__cause__) == "kaboom"


class TestFailClosedResponseShape:
    def test_non_authority_resolution_return_raises_invalid_response(
        self, principal, sale_order
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=NonAuthorityResponseResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        assert exc.value.code == error_codes.INVALID_RESPONSE

    def test_extra_key_in_response_raises_invalid_response(
        self, principal, sale_order
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=ExtraKeyResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        assert exc.value.code == error_codes.INVALID_RESPONSE

    def test_missing_key_raises_model_binding_missing(
        self, principal, sale_order, crm_lead
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=MissingKeyResolver(),
        )
        union = sale_order.union(crm_lead)
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(union, ctx)
        assert exc.value.code == error_codes.MODEL_BINDING_MISSING
        # Deterministic: first absent in request order ⇒ CrmLeadQM (second).
        assert exc.value.model_involved == "CrmLeadQM"

    def test_non_binding_value_raises_invalid_response(
        self, principal, sale_order
    ):
        class BadValueResolver:
            def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
                # Sneak a non-ModelBinding into bindings by bypassing the
                # AuthorityResolution ctor check via __new__ + object.__setattr__.
                # (AuthorityResolution validates on __post_init__, so we
                # construct via a real ModelBinding first then swap.)
                resolution = AuthorityResolution(
                    bindings={"SaleOrderQM": ModelBinding()}
                )
                object.__setattr__(
                    resolution, "bindings", {"SaleOrderQM": "not a binding"}
                )
                return resolution

        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=BadValueResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        assert exc.value.code == error_codes.INVALID_RESPONSE
        assert exc.value.model_involved == "SaleOrderQM"


# ---------------------------------------------------------------------------
# Phase tag
# ---------------------------------------------------------------------------


class TestErrorPhaseTag:
    def test_all_errors_tagged_authority_resolve_phase(
        self, principal, sale_order
    ):
        ctx = ComposeQueryContext(
            principal=principal,
            namespace="odoo",
            authority_resolver=BoomResolver(),
        )
        with pytest.raises(AuthorityResolutionError) as exc:
            resolve_authority_for_plan(sale_order, ctx)
        assert exc.value.phase == error_codes.PHASE_AUTHORITY_RESOLVE
