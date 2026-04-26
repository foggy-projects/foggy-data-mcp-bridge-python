"""Shared fixtures for compose-runtime tests.

Provides the ``_StubResolver`` / ``_StubSemanticService`` test doubles
that several runtime tests would otherwise hand-roll, plus a couple of
convenience builders (``compose_context``, ``runtime_bundle``).

Pre-existing test files (``test_script_runtime.py``,
``test_plan_execution.py``) keep their local helpers — those are old
tests with subtly different stub variants. New tests should consume
these fixtures.

.. versionadded:: 8.2.0.beta (Phase B cleanup)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.runtime import ComposeRuntimeBundle
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)


# ---------------------------------------------------------------------------
# Test doubles (re-exported for tests that need to subclass / customise)
# ---------------------------------------------------------------------------


class StubResolver:
    """Authority resolver that grants every requested model an empty
    :class:`ModelBinding` — i.e. no governance restrictions, no denied
    columns. Sufficient for AST-shape and dispatch tests."""

    def resolve(self, request):
        return AuthorityResolution(bindings={
            mq.model: ModelBinding(
                field_access=None, denied_columns=[], system_slice=[],
            )
            for mq in request.models
        })


class StubSemanticService:
    """Minimum surface for ``run_script`` / ``execute_plan`` round-trips.

    Records every ``execute_sql`` call on ``execute_calls`` so tests can
    assert that database access did (or didn't) happen. Returns a
    sentinel row by default; pass ``rows`` to override.
    """

    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None):
        self._rows = rows if rows is not None else [{"sentinel": "row"}]
        self.execute_calls: List[tuple] = []

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        return list(self._rows)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_resolver() -> StubResolver:
    return StubResolver()


@pytest.fixture
def stub_semantic_service() -> StubSemanticService:
    return StubSemanticService()


@pytest.fixture
def compose_context(stub_resolver: StubResolver) -> ComposeQueryContext:
    """A minimal :class:`ComposeQueryContext` suitable for unit tests
    that don't need tenant / role distinctions."""
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=stub_resolver,
    )


@pytest.fixture
def runtime_bundle(
    compose_context: ComposeQueryContext,
    stub_semantic_service: StubSemanticService,
) -> ComposeRuntimeBundle:
    """Pre-built bundle for tests that need to call
    :func:`set_bundle` directly (e.g. driving
    :meth:`QueryPlan.execute` outside :func:`run_script`)."""
    return ComposeRuntimeBundle(
        ctx=compose_context,
        semantic_service=stub_semantic_service,
        dialect="mysql",
    )


# ---------------------------------------------------------------------------
# Compiler monkeypatch helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_compile_plan(monkeypatch):
    """Patch :func:`compile_plan_to_sql` (and its already-imported alias
    in :mod:`runtime.plan_execution`) to return a sentinel
    :class:`ComposedSql`. Returns the captured-plans list so tests can
    assert how many times the compiler was invoked.

    Both patch targets are required: ``compilation.compiler`` is what
    :meth:`QueryPlan.to_sql` re-imports per call, while
    :mod:`runtime.plan_execution` does ``from ..compilation.compiler
    import compile_plan_to_sql`` at module load and binds the name
    locally — patching only the source module misses that binding.
    """
    captured: List[Any] = []

    def _fake(plan, ctx, *, semantic_service, bindings=None,
             model_info_provider=None, dialect="mysql"):
        captured.append(plan)
        return ComposedSql(
            sql=f"-- fake {type(plan).__name__}\nSELECT 1",
            params=[],
        )

    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.compilation.compiler"
        ".compile_plan_to_sql",
        _fake,
    )
    monkeypatch.setattr(
        "foggy.dataset_model.engine.compose.runtime.plan_execution"
        ".compile_plan_to_sql",
        _fake,
    )
    return captured
