"""v1.7 backlog B-03 · v1.3 engine strict column resolution.

T1-T10 matrix from
``docs/v1.7/P0-v13引擎收紧裸dimension引用-需求.md`` § "测试计划 ·
新增 Python 单测". Each test pins one cell of the new public contract:

* T1-T2: bare dimension / `dim AS alias` → fail-loud with hint.
* T3-T5: `dim$caption` / `dim$id` and the user-alias fix (§"行为 3"
  was the v1.3 silent-drop bug).
* T6: unknown field → generic fail-loud.
* T7-T8: FK-style dimension via `$caption AS userAlias` (covers the
  alias-on-dim path that v1.3 used to silently fall back to TM
  dim.alias).
* T9: inline aggregate path is unchanged.
* T10: F5 dict flattens through the new strict path.

Mirrors the Java ``SemanticQueryServiceV3StrictColumnResolutionTest``
slated for 8.4.0.beta. The error code prefix
``COLUMN_FIELD_NOT_FOUND`` and the dim-attribute whitelist are
contract-aligned across both engines.
"""

from __future__ import annotations

import pytest

from foggy.demo.models.ecommerce_models import (
    create_fact_order_model,
    create_fact_sales_model,
)
from foggy.dataset_model.engine.compose.plan import from_
from foggy.dataset_model.engine.compose.plan.column_normalizer import (
    normalize_columns_to_strings,
)
from foggy.dataset_model.semantic import SemanticQueryService
from foggy.mcp_spi.semantic import SemanticQueryRequest


@pytest.fixture
def svc() -> SemanticQueryService:
    s = SemanticQueryService()
    s.register_model(create_fact_sales_model())
    s.register_model(create_fact_order_model())
    return s


def _build(svc, columns, **extra) -> str:
    """Helper: build SQL for FactSalesModel with the given columns and
    return the response. Use ``mode="validate"`` so executor isn't needed.
    """
    req = SemanticQueryRequest(columns=list(columns), **extra)
    return svc.query_model("FactSalesModel", req, mode="validate")


class TestStrictColumnResolution:
    # --- Reject paths -------------------------------------------------------

    def test_t1_bare_dimension_fails_with_hint(self, svc):
        """T1 · ``["orderStatus"]`` → fail-loud + hint ``orderStatus$caption``."""
        with pytest.raises(ValueError) as ei:
            svc._build_query(svc.get_model("FactSalesModel"),
                             SemanticQueryRequest(columns=["orderStatus"]))
        msg = str(ei.value)
        assert "COLUMN_FIELD_NOT_FOUND" in msg
        assert "orderStatus" in msg
        assert "did you mean 'orderStatus$caption'" in msg

    def test_t2_bare_dim_with_as_fails_with_hint(self, svc):
        """T2 · ``["orderStatus AS s"]`` → fail-loud + hint that
        suggests the ``$caption AS s`` form preserving the user alias."""
        with pytest.raises(ValueError) as ei:
            svc._build_query(svc.get_model("FactSalesModel"),
                             SemanticQueryRequest(columns=["orderStatus AS s"]))
        msg = str(ei.value)
        assert "COLUMN_FIELD_NOT_FOUND" in msg
        assert "did you mean 'orderStatus$caption AS s'" in msg

    def test_t6_unknown_field_fails(self, svc):
        """T6 · ``["unknownField"]`` → generic ``COLUMN_FIELD_NOT_FOUND``
        listing the valid forms."""
        with pytest.raises(ValueError) as ei:
            svc._build_query(svc.get_model("FactSalesModel"),
                             SemanticQueryRequest(columns=["unknownField"]))
        msg = str(ei.value)
        assert "COLUMN_FIELD_NOT_FOUND" in msg
        assert "unknownField" in msg
        assert "Valid forms are" in msg

    # --- Accept paths -------------------------------------------------------

    def test_t3_dim_caption_compiles(self, svc):
        """T3 · ``["orderStatus$caption"]`` → ``t.order_status AS "<TM caption>"``."""
        r = _build(svc, ["orderStatus$caption"])
        assert r.error is None, r.error
        assert "t.order_status" in r.sql

    def test_t4_dim_caption_with_user_alias_overrides_tm_caption(self, svc):
        """T4 (★ 关键) · ``["orderStatus$caption AS userAlias"]`` →
        SQL alias is the user-supplied identifier, not the TM-declared
        ``dimension.alias``. This is the bug fix for B-03 § "行为 3"."""
        r = _build(svc, ["orderStatus$caption AS userAlias"])
        assert r.error is None, r.error
        assert "t.order_status" in r.sql
        # The new alias must appear; the TM alias ("订单状态") must NOT.
        assert "userAlias" in r.sql
        assert "订单状态" not in r.sql

    def test_t5_dim_id_compiles(self, svc):
        """T5 · ``["orderStatus$id"]`` — self-attr dim, ``$id`` resolves
        to the same physical column as ``$caption``."""
        r = _build(svc, ["orderStatus$id"])
        assert r.error is None, r.error
        assert "t.order_status" in r.sql

    def test_t7_fk_dim_caption_compiles(self, svc):
        """T7 · FK-style dim via ``$caption`` resolves through the
        join_def caption SQL path (covers the join branch in
        ``resolve_field_strict``)."""
        # FactOrderModel's ``customer`` is a join_def-attached dim
        req = SemanticQueryRequest(columns=["customer$caption"])
        r = svc.query_model("FactOrderModel", req, mode="validate")
        assert r.error is None, r.error

    def test_t8_fk_dim_caption_with_user_alias(self, svc):
        """T8 · FK-style dim ``customer$caption AS customerName`` →
        user alias survives end-to-end through the join path."""
        req = SemanticQueryRequest(columns=["customer$caption AS customerName"])
        r = svc.query_model("FactOrderModel", req, mode="validate")
        assert r.error is None, r.error
        assert "customerName" in r.sql

    def test_t9_inline_aggregate_path_unchanged(self, svc):
        """T9 · inline aggregate path stays first in the loop and keeps
        producing aggregate SQL when the operand and alias are both
        valid."""
        r = _build(svc, ["SUM(salesAmount) AS total"])
        assert r.error is None, r.error
        assert "SUM(t.sales_amount)" in r.sql
        assert "total" in r.sql

    def test_t10_f5_dict_flattens_through_strict_path(self, svc):
        """T10 · F5 ``{plan, field}`` dict normalises to the same
        F4 string and routes through the strict resolver."""
        sales = from_(model="FactSalesModel", columns=["orderStatus$caption"])
        # Manually emulate what column_normalizer produces for an F5 dict
        # at parse time — the strict resolver must accept the flattened
        # output identically.
        flattened = normalize_columns_to_strings(
            [{"plan": sales, "field": "orderStatus$caption"}]
        )
        assert flattened == ["orderStatus$caption"]
        r = _build(svc, flattened)
        assert r.error is None, r.error
        assert "t.order_status" in r.sql
