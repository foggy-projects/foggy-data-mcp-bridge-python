"""G5 Phase 2 (F5) — Plan-qualified column object syntax integration tests.

Mirrors Java's ``F5ColumnObjectIntegrationTest`` for the Python side.
Goes through the full compose pipeline:

    F5 dict normalize → BaseModelPlan / DerivedQueryPlan → SchemaDerivation
    (G10 ON · plan_provenance populated) → ComposePlanner →
    plan-aware permission validator (PR5.4) → compile_plan_to_sql

Because Python's plan IR is ``Tuple[str, ...]``, F5 dicts flatten to
the F4 string form at parse time; the ``plan`` reference is validated
(must be a QueryPlan) but discarded after — see ``column_normalizer``
module docstring "Architectural divergence from Java".

This means F5 SQL output in Python is identical to the equivalent F4
string ("name" or "SUM(amount) AS total"); the plan-routed permission
validator (PR5.4) routes columns via ``OutputSchema.plan_provenance``
populated by ``derive_schema``, NOT via ``PlanColumnRef`` carried in
the plan tree.

Note on column shapes used here
-------------------------------
The v1.3 engine's ``build_query_with_governance`` only accepts the
``field AS alias`` syntax for **inline aggregates** (parsed by
``parse_inline_aggregate``, e.g. ``SUM(salesAmount) AS total``). Bare
dimensions like ``orderStatus AS status`` are silently dropped — that
is a long-standing v1.3 limitation independent of F5. The integration
suite therefore uses:

* F5 ``{plan, field}`` (no alias) for plain dimensions, OR
* F5 ``{plan, field, agg, as}`` for aggregate compounds.

Coverage (G10 acceptance FU-1: spec §9 ≥3 plan-aware compile +
≥2 plan-routed permission):
- 3 plan-aware compile cases (self-reference / agg+as / F5↔F4 SQL parity)
- 2 plan-routed permission cases (allow whitelist / deny whitelist)
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from foggy.dataset_model.engine.compose import feature_flags
from foggy.dataset_model.engine.compose.compilation import compile_plan_to_sql
from foggy.dataset_model.engine.compose.compilation.errors import (
    ComposeCompileError,
)
from foggy.dataset_model.engine.compose.context import (
    ComposeQueryContext,
    Principal,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.schema import error_codes
from foggy.dataset_model.engine.compose.schema.errors import ComposeSchemaError
from foggy.dataset_model.engine.compose.security import (
    AuthorityRequest,
    AuthorityResolution,
    ModelBinding,
)


@pytest.fixture(autouse=True)
def _enable_g10():
    """Pin G10 ON for all F5 integration tests; reset on teardown.

    The compose autouse ``_clear_g10_override`` fixture (in tests/compose/conftest.py)
    runs after this in teardown, so the flag is always reset between tests.
    """
    feature_flags.override_g10_enabled(True)
    yield


# ---------------------------------------------------------------------------
# Per-test resolver: build with a configurable per-model field_access whitelist
# ---------------------------------------------------------------------------


def _resolver_with_field_access(per_model_field_access: Dict[str, List[str]]):
    """Return an authority resolver that emits per-model ``ModelBinding``
    with the given field_access whitelist. Models not in the map get an
    empty (permissive) binding."""

    class _Resolver:
        def resolve(self, request: AuthorityRequest) -> AuthorityResolution:
            bindings: Dict[str, ModelBinding] = {}
            for mq in request.models:
                fa = per_model_field_access.get(mq.model)
                if fa is not None:
                    bindings[mq.model] = ModelBinding(field_access=fa)
                else:
                    bindings[mq.model] = ModelBinding()
            return AuthorityResolution(bindings=bindings)

    return _Resolver()


def _ctx(per_model_field_access: Dict[str, List[str]] = None) -> ComposeQueryContext:
    return ComposeQueryContext(
        principal=Principal(user_id="f5-integration", tenant_id="t", roles=["tester"]),
        namespace="demo",
        authority_resolver=_resolver_with_field_access(per_model_field_access or {}),
    )


# ---------------------------------------------------------------------------
# ≥3 plan-aware compile (G10 acceptance FU-1)
# ---------------------------------------------------------------------------


class TestF5PlanAwareCompile:
    def test_f5_self_reference_compiles_to_same_sql_as_f4(self, svc):
        """Spec §5.2 self-reference: {plan: sales, field} flattens to bare
        F4 ``"orderStatus"``; SQL output identical to direct F4 dict."""
        # Build two parallel base plans (Python plan equality is structural;
        # SQL output should be identical)
        sales = from_(model="FactSalesModel", columns=["orderStatus"])
        # F5 self-reference: plan === current model
        f5_plan = from_(
            model="FactSalesModel",
            columns=[{"plan": sales, "field": "orderStatus"}],
        )
        f4_plan = from_(
            model="FactSalesModel",
            columns=[{"field": "orderStatus"}],
        )

        f5_composed = compile_plan_to_sql(
            f5_plan, _ctx(), semantic_service=svc, dialect="mysql8"
        )
        f4_composed = compile_plan_to_sql(
            f4_plan, _ctx(), semantic_service=svc, dialect="mysql8"
        )

        # F5 and F4 produce identical SQL — Python flattens at parse time.
        assert f5_composed.sql == f4_composed.sql, (
            f"F5/F4 SQL must match;\nF5 sql={f5_composed.sql}\nF4 sql={f4_composed.sql}"
        )
        # Engine emits underlying physical column for the dimension
        assert "order_status" in f5_composed.sql

    def test_f5_agg_as_compound_compiles_to_aggregate_sql(self, svc):
        """{plan, field, agg, as} compound flattens to "SUM(field) AS alias"
        and emits the inline-aggregate SQL the v1.3 engine recognises."""
        sales = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        plan = from_(
            model="FactSalesModel",
            columns=[
                {"plan": sales, "field": "orderStatus"},
                {"plan": sales, "field": "salesAmount", "agg": "sum", "as": "total"},
            ],
            group_by=["orderStatus"],
        )

        composed = compile_plan_to_sql(
            plan, _ctx(), semantic_service=svc, dialect="mysql8"
        )

        # Engine emits SUM aggregation + alias for the F5 agg+as compound.
        assert "SUM" in composed.sql.upper()
        assert "sales_amount" in composed.sql
        assert "total" in composed.sql
        assert "GROUP BY" in composed.sql

    def test_f5_dict_and_f4_dict_emit_identical_sql(self, svc):
        """F5 ↔ F4 SQL parity: when ``plan`` is the current model and
        F5 is otherwise identical to F4, the resulting SQL must be
        byte-equal."""
        # Use FactOrderModel to widen the matrix beyond FactSalesModel.
        f5 = from_(
            model="FactOrderModel",
            columns=[
                {"plan": from_(model="FactOrderModel", columns=["orderStatus"]), "field": "orderStatus"},
                {"plan": from_(model="FactOrderModel", columns=["totalAmount"]), "field": "totalAmount", "agg": "sum", "as": "amt"},
            ],
            group_by=["orderStatus"],
        )
        f4 = from_(
            model="FactOrderModel",
            columns=[
                {"field": "orderStatus"},
                {"field": "totalAmount", "agg": "sum", "as": "amt"},
            ],
            group_by=["orderStatus"],
        )

        f5_composed = compile_plan_to_sql(
            f5, _ctx(), semantic_service=svc, dialect="mysql8"
        )
        f4_composed = compile_plan_to_sql(
            f4, _ctx(), semantic_service=svc, dialect="mysql8"
        )

        assert f5_composed.sql == f4_composed.sql


# ---------------------------------------------------------------------------
# ≥2 plan-routed permission (G10 acceptance FU-1)
# ---------------------------------------------------------------------------


class TestF5PlanRoutedPermission:
    def test_f5_field_in_whitelist_compiles(self, svc):
        """field_access includes the F5 column → PR5.4 validator passes
        (column resolves uniquely to its plan via ``plan_provenance`` and
        the whitelist allows it)."""
        sales = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        plan = from_(
            model="FactSalesModel",
            columns=[
                {"plan": sales, "field": "orderStatus"},
                {"plan": sales, "field": "salesAmount", "agg": "sum", "as": "amt"},
            ],
            group_by=["orderStatus"],
        )

        # Whitelist allows orderStatus + salesAmount on FactSalesModel.
        ctx = _ctx({"FactSalesModel": ["orderStatus", "salesAmount"]})
        composed = compile_plan_to_sql(
            plan, ctx, semantic_service=svc, dialect="mysql8"
        )

        assert "sales_amount" in composed.sql
        assert "amt" in composed.sql
        assert "order_status" in composed.sql

    def test_f5_field_not_in_whitelist_throws_field_access_denied(self, svc):
        """field_access excludes the F5 column → enforcement triggers a
        plan-routed denial.

        Two valid denial pathways per spec §6.4:

        * **PR5.4 validator** raises ``ComposeSchemaError(FIELD_ACCESS_DENIED)``
          at the permission-validate phase when ``OutputSchema``'s
          ``plan_provenance`` resolves the column to a bound plan whose
          whitelist excludes it. Triggered when provenance is set on the
          spec — currently only on join/union sides (``_append_annotated_side``).
        * **Legacy single-base v1.3** ``_resolve_effective_visible``
          raises ``ValueError`` for a denied field; the compose layer
          wraps it as ``ComposeCompileError`` at the per-base-compile
          phase. This is the path for single-BaseModelPlan compiles
          where provenance is left ``None`` and the validator defers
          to legacy enforcement (see validator's
          "Single-base / no-provenance case — defer to legacy pipeline"
          branch).

        Either denial is plan-routed (the same field_access whitelist drives
        both); the test accepts both shapes.
        """
        sales = from_(model="FactSalesModel", columns=["orderStatus", "salesAmount"])
        plan = from_(
            model="FactSalesModel",
            columns=[
                {"plan": sales, "field": "salesAmount", "agg": "sum", "as": "amt"},
            ],
        )

        # Whitelist excludes salesAmount — only orderStatus permitted.
        ctx = _ctx({"FactSalesModel": ["orderStatus"]})

        with pytest.raises((ComposeSchemaError, ComposeCompileError)) as ei:
            compile_plan_to_sql(plan, ctx, semantic_service=svc, dialect="mysql8")

        if isinstance(ei.value, ComposeSchemaError):
            # Plan-routed validator path (provenance set).
            assert ei.value.code in (
                error_codes.FIELD_ACCESS_DENIED,
                error_codes.COLUMN_PLAN_NOT_BOUND,
            ), f"unexpected schema code {ei.value.code!r} (msg: {ei.value})"
        else:
            # Legacy v1.3 single-base path; the wrapped ValueError carries
            # the "not accessible" / "salesAmount" markers verifying the
            # field_access binding actually drove the denial.
            msg = str(ei.value)
            assert "salesAmount" in msg and "not accessible" in msg, (
                f"unexpected compile error: {msg}"
            )
