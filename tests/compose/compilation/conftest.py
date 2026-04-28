"""Shared fixtures for M6 compilation tests.

Builds a real ``SemanticQueryService`` backed by demo ecommerce models
plus a Principal / AuthorityResolver / ComposeQueryContext so tests
exercise the live v1.3 ``_build_query`` path rather than mocks.

Tests that want to stub the service (e.g. "error path when _build_query
raises") can still do so locally via ``monkeypatch`` — the shared
service fixture is just the default.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose.context import (
    ComposeQueryContext,
    Principal,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
)
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.demo.models.ecommerce_models import (
    create_fact_sales_model,
    create_fact_order_model,
    create_fact_payment_model,
)


# ---------------------------------------------------------------------------
# SemanticQueryService + registered demo models
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> SemanticQueryService:
    """SemanticQueryService with three demo models registered.

    All tests share the same TableModel shapes (FactSalesModel,
    FactOrderModel, FactPaymentModel) so assertions can reference
    concrete column names from the ecommerce demo.
    """
    s = SemanticQueryService()
    s.register_model(create_fact_sales_model())
    s.register_model(create_fact_order_model())
    s.register_model(create_fact_payment_model())
    return s


# ---------------------------------------------------------------------------
# ComposeQueryContext
# ---------------------------------------------------------------------------


class _PermissiveResolver:
    """Returns an empty ``ModelBinding`` for every requested model.

    Good enough for M6 compilation tests that focus on SQL shape — the
    binding three-field injection test (6.4) uses a tailored resolver
    per case.
    """

    def __init__(self) -> None:
        self.calls: List[AuthorityRequest] = []

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        self.calls.append(request)
        return AuthorityResolution(
            bindings={mq.model: ModelBinding() for mq in request.models}
        )


@pytest.fixture
def principal() -> Principal:
    return Principal(user_id="tester", tenant_id="t001", roles=["analyst"])


@pytest.fixture
def permissive_resolver() -> _PermissiveResolver:
    return _PermissiveResolver()


@pytest.fixture
def ctx(principal: Principal, permissive_resolver: _PermissiveResolver) -> ComposeQueryContext:
    """A ComposeQueryContext with an empty-binding resolver — tests that
    care about a specific binding shape override with a custom resolver."""
    return ComposeQueryContext(
        principal=principal,
        namespace="demo",
        authority_resolver=permissive_resolver,
    )


# ---------------------------------------------------------------------------
# Plan builders (convenience wrappers around ``from_``)
# ---------------------------------------------------------------------------


@pytest.fixture
def base_sales():
    """BaseModelPlan(FactSalesModel, columns=[orderStatus, salesAmount])."""
    return from_(
        model="FactSalesModel",
        columns=["orderStatus$caption", "salesAmount"],
    )


@pytest.fixture
def base_orders():
    """BaseModelPlan(FactOrderModel, columns=[orderStatus, totalAmount])."""
    return from_(
        model="FactOrderModel",
        columns=["orderStatus$caption", "totalAmount"],
    )


@pytest.fixture
def base_payments():
    """BaseModelPlan(FactPaymentModel, columns=[payMethod, payAmount])."""
    return from_(
        model="FactPaymentModel",
        columns=["payMethod$caption", "payAmount"],
    )


# ---------------------------------------------------------------------------
# Custom resolver factory for binding-injection tests (6.4)
# ---------------------------------------------------------------------------


class _FixedBindingResolver:
    """Returns pre-configured ``ModelBinding`` per QM model name.

    Use this in 6.4 tests where we want to verify that a specific
    binding (field_access / denied_columns / system_slice) is injected
    into ``SemanticQueryRequest`` and honored by the v1.3 engine.
    """

    def __init__(self, mapping: Dict[str, ModelBinding]) -> None:
        self._mapping = mapping
        self.calls: List[AuthorityRequest] = []

    def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
        self.calls.append(request)
        return AuthorityResolution(
            bindings={
                mq.model: self._mapping.get(mq.model, ModelBinding())
                for mq in request.models
            }
        )


@pytest.fixture
def make_fixed_resolver():
    """Factory fixture: tests call ``make_fixed_resolver({model: binding})``
    to get a resolver + context + bindings dict in one go."""

    def _make(mapping: Dict[str, ModelBinding]):
        return _FixedBindingResolver(mapping)

    return _make
