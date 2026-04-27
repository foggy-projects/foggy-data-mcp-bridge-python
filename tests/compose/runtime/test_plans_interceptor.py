"""Unit tests for ``plans_interceptor.intercept_plans`` — the post-script
``{ plans, metadata }`` envelope handler that auto-evaluates
:class:`QueryPlan` instances inside the envelope.

Covers the three envelope shapes (dict / list / single), pass-through
of non-envelope inputs, the ``preview_mode`` flag (``.execute()`` vs
``.to_sql()``), and the identity-unchanged short-circuit for
literal-only ``plans`` values.

These tests do NOT exercise the full FSScript pipeline — see
``test_js_fixture_parity.py`` for that layer. The local ``_FakePlan``
test double avoids any need for a real semantic service or bundle.

.. versionadded:: 8.2.0.beta (Phase B)
"""

from __future__ import annotations

import pytest

from foggy.dataset_model.engine.compose.plan.plan import QueryPlan
from foggy.dataset_model.engine.compose.runtime.plans_interceptor import (
    intercept_plans,
)


# ---------------------------------------------------------------------------
# Fake plan that records execute / to_sql calls and returns predictable
# sentinels — saves us the cost of wiring up a real semantic service /
# bundle for these unit tests.
# ---------------------------------------------------------------------------


class _FakePlan(QueryPlan):
    """A no-op :class:`QueryPlan` subclass that records dispatch calls.

    Inheriting from :class:`QueryPlan` is the cheapest way to satisfy
    ``isinstance(x, QueryPlan)`` checks in the interceptor without
    pulling in real plan validation.
    """

    def __init__(self, name: str):
        # QueryPlan's frozen-dataclass subclasses assume __init__ is
        # synthesised; we don't call super().__init__ because the ABC
        # has no init.
        self.name = name
        self.execute_calls = 0
        self.to_sql_calls = 0

    def execute(self, context=None):  # type: ignore[override]
        self.execute_calls += 1
        return [{"row": self.name}]

    def to_sql(self, context=None, *, dialect=None):  # type: ignore[override]
        self.to_sql_calls += 1
        return f"SQL FOR {self.name}"

    def base_model_plans(self):  # type: ignore[override]
        return ()

    def collect_visible_plans(self):  # type: ignore[override]
        # G5 Phase 2 (F5) abstract — leaf-style stub for the fake plan
        return (self,)


# ---------------------------------------------------------------------------
# Pass-through behaviour: non-envelope inputs are returned verbatim.
# ---------------------------------------------------------------------------


class TestPassThrough:
    def test_none_returns_none(self):
        assert intercept_plans(None) is None

    def test_int_returns_int(self):
        assert intercept_plans(42) == 42

    def test_string_returns_string(self):
        assert intercept_plans("hello") == "hello"

    def test_list_without_envelope_returns_list_unchanged(self):
        rows = [{"id": 1}, {"id": 2}]
        assert intercept_plans(rows) is rows

    def test_dict_without_plans_key_returns_dict_unchanged(self):
        d = {"metadata": {"title": "x"}, "rows": [1, 2]}
        out = intercept_plans(d)
        # Dict-without-plans is passed through verbatim — no copy needed.
        assert out is d

    def test_bare_query_plan_passes_through_python_divergence(self):
        """Python diverges from Java here: bare ``QueryPlan`` returns
        pass through (no auto-execute) so unit tests can keep asserting
        on AST shape. See ``plans_interceptor`` module docstring §
        "Divergence from Java"."""
        p = _FakePlan("p1")
        out = intercept_plans(p)
        assert out is p
        assert p.execute_calls == 0
        assert p.to_sql_calls == 0


# ---------------------------------------------------------------------------
# Envelope detection: dict with ``plans`` key.
# ---------------------------------------------------------------------------


class TestEnvelopeDictPlans:
    def test_named_plan_map_executes_each_plan(self):
        p1 = _FakePlan("p1")
        p2 = _FakePlan("p2")
        envelope = {
            "plans": {"summary": p1, "detail": p2},
            "metadata": {"title": "T"},
        }
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"]["summary"] == [{"row": "p1"}]
        assert out["plans"]["detail"] == [{"row": "p2"}]
        assert p1.execute_calls == 1
        assert p2.execute_calls == 1
        assert p1.to_sql_calls == 0
        assert p2.to_sql_calls == 0

    def test_named_plan_map_preview_mode_uses_to_sql(self):
        p1 = _FakePlan("p1")
        envelope = {
            "plans": {"x": p1},
            "metadata": {"title": "T"},
        }
        out = intercept_plans(envelope, preview_mode=True)
        assert out["plans"]["x"] == "SQL FOR p1"
        assert p1.to_sql_calls == 1
        assert p1.execute_calls == 0

    def test_metadata_passes_through_unchanged(self):
        p1 = _FakePlan("p1")
        meta = {"title": "T", "tags": ["a", "b"]}
        envelope = {"plans": {"x": p1}, "metadata": meta}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["metadata"] is meta  # same object, not copied/mutated

    def test_extra_envelope_keys_pass_through(self):
        """``intercept_plans`` only touches ``plans``; any other keys
        on the envelope dict survive verbatim."""
        envelope = {
            "plans": {"x": _FakePlan("p")},
            "metadata": {"title": "T"},
            "warnings": ["hello"],
            "trace_id": "abc-123",
        }
        out = intercept_plans(envelope, preview_mode=False)
        assert out["warnings"] == ["hello"]
        assert out["trace_id"] == "abc-123"

    def test_non_plan_values_in_named_map_pass_through(self):
        """If the script puts a literal next to a plan inside the
        ``plans`` dict (e.g. a hardcoded label), it should survive."""
        p = _FakePlan("p")
        envelope = {
            "plans": {
                "real": p,
                "literal": {"hardcoded": True},
                "number": 42,
            },
            "metadata": {},
        }
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"]["real"] == [{"row": "p"}]
        assert out["plans"]["literal"] == {"hardcoded": True}
        assert out["plans"]["number"] == 42

    def test_does_not_mutate_input_envelope(self):
        """The script's literal dict must not be mutated — interception
        produces a NEW dict so the caller can safely re-use the input."""
        p = _FakePlan("p")
        original_plans = {"x": p}
        envelope = {"plans": original_plans, "metadata": {}}
        intercept_plans(envelope, preview_mode=False)
        # Original plans dict still has the QueryPlan, not the rows.
        assert envelope["plans"] is original_plans
        assert envelope["plans"]["x"] is p


class TestEnvelopeListPlans:
    def test_ordered_plan_list_executes_each(self):
        p1, p2 = _FakePlan("p1"), _FakePlan("p2")
        envelope = {"plans": [p1, p2], "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == [[{"row": "p1"}], [{"row": "p2"}]]

    def test_ordered_plan_list_preview_mode(self):
        p1, p2 = _FakePlan("p1"), _FakePlan("p2")
        envelope = {"plans": [p1, p2], "metadata": {}}
        out = intercept_plans(envelope, preview_mode=True)
        assert out["plans"] == ["SQL FOR p1", "SQL FOR p2"]

    def test_tuple_treated_like_list(self):
        """Some scripts/converters might emit a tuple instead of a
        list — interceptor accepts both shapes."""
        p1 = _FakePlan("p1")
        envelope = {"plans": (p1,), "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == [[{"row": "p1"}]]

    def test_list_with_mixed_plans_and_literals(self):
        p = _FakePlan("p")
        envelope = {"plans": [p, "label", 42], "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == [[{"row": "p"}], "label", 42]


class TestEnvelopeSinglePlan:
    """When ``plans`` is a single :class:`QueryPlan` (not wrapped in
    dict / list), the interceptor evaluates it directly."""

    def test_single_plan_executes(self):
        p = _FakePlan("p")
        envelope = {"plans": p, "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == [{"row": "p"}]

    def test_single_plan_preview(self):
        p = _FakePlan("p")
        envelope = {"plans": p, "metadata": {}}
        out = intercept_plans(envelope, preview_mode=True)
        assert out["plans"] == "SQL FOR p"


class TestEnvelopeUnknownPlansShape:
    """Defensive: if ``plans`` is something we don't recognise, the
    interceptor logs a warning and passes the value through. Better
    than silently raising — scripts in the wild may have bugs."""

    def test_int_plans_passes_through(self, caplog):
        envelope = {"plans": 42, "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == 42

    def test_string_plans_passes_through(self):
        envelope = {"plans": "not a plan", "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out["plans"] == "not a plan"


class TestIdentityShortCircuit:
    """Phase B optimisation: when ``plans`` contains no
    :class:`QueryPlan` instances at all, ``intercept_plans`` MUST return
    the input dict unchanged (same identity) instead of allocating a
    new envelope dict. Verifies we don't pay the dict-copy cost for
    literal-only scripts."""

    def test_dict_plans_with_no_query_plans_returns_input_identity(self):
        """All-literal dict inside ``plans`` — interceptor copies nothing."""
        envelope = {
            "plans": {"label": "no-op", "count": 0, "items": [1, 2]},
            "metadata": {"title": "T"},
        }
        out = intercept_plans(envelope, preview_mode=False)
        assert out is envelope

    def test_list_plans_with_no_query_plans_returns_input_identity(self):
        """All-literal list inside ``plans`` — same short-circuit."""
        envelope = {"plans": ["a", "b", 42], "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out is envelope

    def test_unknown_plans_shape_returns_input_identity(self):
        """``plans=42`` (warning branch) also passes the envelope
        through unchanged — no point copying."""
        envelope = {"plans": 42, "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out is envelope

    def test_dict_plans_with_one_real_plan_does_copy(self):
        """Sanity check: when a real plan is present, the envelope IS
        copied (otherwise mutation would leak)."""
        p = _FakePlan("p")
        envelope = {"plans": {"real": p, "label": "ok"}, "metadata": {}}
        out = intercept_plans(envelope, preview_mode=False)
        assert out is not envelope
        assert envelope["plans"]["real"] is p  # original unmutated
