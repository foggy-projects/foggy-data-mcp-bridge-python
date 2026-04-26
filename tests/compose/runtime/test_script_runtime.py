"""Tests for ``run_script`` + evaluator lockdown."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from foggy.dataset_model.engine.compose import ComposedSql
from foggy.dataset_model.engine.compose.context.compose_query_context import (
    ComposeQueryContext,
)
from foggy.dataset_model.engine.compose.context.principal import Principal
from foggy.dataset_model.engine.compose.plan import BaseModelPlan, from_
from foggy.dataset_model.engine.compose.runtime import (
    ALLOWED_SCRIPT_GLOBALS,
    ScriptResult,
    run_script,
)
from foggy.dataset_model.engine.compose.security import (
    AuthorityResolution,
    ModelBinding,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubResolver:
    def resolve(self, request):
        return AuthorityResolution(bindings={
            mq.model: ModelBinding() for mq in request.models
        })


class _StubSemanticService:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [{"id": 1}]
        self.execute_calls: List = []

    def execute_sql(self, sql, params, *, route_model=None):
        self.execute_calls.append((sql, list(params), route_model))
        return list(self.rows)


def _ctx(resolver=None):
    return ComposeQueryContext(
        principal=Principal(user_id="u1"),
        namespace="default",
        authority_resolver=resolver or _StubResolver(),
    )


# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------


def test_empty_script_returns_none_value():
    r = run_script("", _ctx(), semantic_service=_StubSemanticService())
    assert isinstance(r, ScriptResult)
    assert r.value is None


def test_whitespace_only_script_returns_none_value():
    r = run_script("   \n  ", _ctx(), semantic_service=_StubSemanticService())
    assert r.value is None


def test_ctx_required():
    with pytest.raises(ValueError, match="ctx is required"):
        run_script("1+1", ctx=None, semantic_service=_StubSemanticService())


def test_semantic_service_required():
    with pytest.raises(ValueError, match="semantic_service is required"):
        run_script("1+1", _ctx(), semantic_service=None)


# ---------------------------------------------------------------------------
# Basic evaluation
# ---------------------------------------------------------------------------


def test_literal_expression_result():
    r = run_script("1 + 2", _ctx(), semantic_service=_StubSemanticService())
    assert r.value == 3


def test_top_level_return_captured():
    r = run_script(
        "return 'hello';", _ctx(), semantic_service=_StubSemanticService()
    )
    assert r.value == "hello"


# ---------------------------------------------------------------------------
# from() / dsl() DSL entry
# ---------------------------------------------------------------------------


def test_from_creates_base_model_plan():
    r = run_script(
        'from({model: "Sales", columns: ["id"]})',
        _ctx(), semantic_service=_StubSemanticService(),
    )
    assert isinstance(r.value, BaseModelPlan)
    assert r.value.model == "Sales"


def test_dsl_alias_equivalent_to_from():
    r = run_script(
        'dsl({model: "Sales", columns: ["id"]})',
        _ctx(), semantic_service=_StubSemanticService(),
    )
    assert isinstance(r.value, BaseModelPlan)


# ---------------------------------------------------------------------------
# Evaluator lockdown — allowed globals + no import
# ---------------------------------------------------------------------------


def test_module_loader_and_bean_registry_are_disabled():
    """M7 hard contract: evaluator is constructed with
    ``module_loader=None`` + ``bean_registry=None``. Assert the helper
    that actually wires the evaluator (``_evaluate_program``) keeps the
    "no arbitrary import / @bean" red line."""
    import inspect
    from foggy.dataset_model.engine.compose.runtime import script_runtime

    src = inspect.getsource(script_runtime._evaluate_program)
    assert "module_loader=None" in src
    assert "bean_registry=None" in src


def test_undefined_name_raises():
    """Calling a non-whitelisted name like ``process`` raises since the
    evaluator has no such binding."""
    with pytest.raises(Exception):
        run_script(
            "some_undefined_fn()",
            _ctx(),
            semantic_service=_StubSemanticService(),
        )


def test_allowed_script_globals_contains_compose_entry_points():
    assert "from" in ALLOWED_SCRIPT_GLOBALS
    assert "dsl" in ALLOWED_SCRIPT_GLOBALS


def test_allowed_script_globals_includes_fsscript_builtins():
    for name in ("JSON", "parseInt", "Array", "Object", "Function",
                 "typeof", "isNaN", "isFinite",
                 "String", "Number", "Boolean",
                 "parseFloat", "toString"):
        assert name in ALLOWED_SCRIPT_GLOBALS, f"{name!r} missing"


def test_evaluator_context_keys_match_allowed_globals():
    """Boot run_script with an empty program and hard-assert the
    evaluator's visible surface matches ALLOWED_SCRIPT_GLOBALS (after
    filtering internal ``__*__`` entries and the Array_* / Console_*
    function families)."""

    # We poke the script_runtime module to capture the live evaluator.
    from foggy.dataset_model.engine.compose.runtime import script_runtime as sr

    captured: Dict[str, Any] = {}
    real_evaluator_cls = sr.ExpressionEvaluator

    def probe(*args, **kwargs):
        ev = real_evaluator_cls(*args, **kwargs)
        captured["ev"] = ev
        return ev

    try:
        sr.ExpressionEvaluator = probe  # type: ignore[assignment]
        r = run_script("1", _ctx(), semantic_service=_StubSemanticService())
    finally:
        sr.ExpressionEvaluator = real_evaluator_cls  # type: ignore[assignment]
    assert r.value == 1

    ev = captured["ev"]
    raw_keys = set(ev.context.keys())
    # Strip internal dunders and the Array_* / Console_* families
    cleaned = {
        k for k in raw_keys
        if not k.startswith("__")
        and not k.startswith("Array_")
        and not k.startswith("Console_")
    }
    assert cleaned == ALLOWED_SCRIPT_GLOBALS, (
        f"Unexpected evaluator-visible names: "
        f"extras={cleaned - ALLOWED_SCRIPT_GLOBALS}; "
        f"missing={ALLOWED_SCRIPT_GLOBALS - cleaned}"
    )


def test_evaluator_does_not_expose_host_infrastructure():
    """Make sure host secrets (semantic_service / bundle / ComposeQueryContext)
    are NOT visible in the evaluator."""
    from foggy.dataset_model.engine.compose.runtime import script_runtime as sr

    captured: Dict[str, Any] = {}
    real = sr.ExpressionEvaluator

    def probe(*args, **kwargs):
        ev = real(*args, **kwargs)
        captured["ev"] = ev
        return ev

    try:
        sr.ExpressionEvaluator = probe  # type: ignore[assignment]
        run_script("1", _ctx(), semantic_service=_StubSemanticService())
    finally:
        sr.ExpressionEvaluator = real  # type: ignore[assignment]

    keys = list(captured["ev"].context.keys())
    for forbidden in (
        "ctx", "context", "semantic_service", "bundle", "executor",
        "authority_resolver", "principal", "runtime",
    ):
        assert forbidden not in keys, (
            f"{forbidden!r} unexpectedly visible to script"
        )


# ---------------------------------------------------------------------------
# SQL/params best-effort capture
# ---------------------------------------------------------------------------


def test_script_result_captures_sql_when_value_is_composed_sql():
    """If script returns a ComposedSql-like object, ScriptResult should
    lift sql/params."""
    from foggy.dataset_model.engine.compose.runtime import script_runtime as sr

    # Fake from that returns a ComposedSql-looking dataclass bound by
    # the evaluator. We inject it via the `from` function override to
    # bypass the compile pipeline entirely.
    original_from = sr._from_dsl

    def fake_from(*args, **kwargs):
        return ComposedSql(sql="SELECT 42", params=[42])

    try:
        sr._from_dsl = fake_from  # type: ignore[assignment]
        r = run_script(
            'from({model: "Any", columns: ["id"]})',
            _ctx(), semantic_service=_StubSemanticService(),
        )
    finally:
        sr._from_dsl = original_from  # type: ignore[assignment]
    assert r.sql == "SELECT 42"
    assert r.params == [42]


# ---------------------------------------------------------------------------
# No eval / exec literal in the runtime source
# ---------------------------------------------------------------------------


def test_runtime_source_contains_no_literal_eval_or_exec():
    """M7 hard red line (prompt §必读前置 #0): runtime source must not
    invoke Python's ``eval`` / ``exec`` / ``__import__``."""
    import os
    import foggy.dataset_model.engine.compose.runtime as runtime_pkg

    runtime_dir = os.path.dirname(runtime_pkg.__file__)
    violations = []
    for fname in os.listdir(runtime_dir):
        if not fname.endswith(".py"):
            continue
        with open(os.path.join(runtime_dir, fname), encoding="utf-8") as f:
            text = f.read()
        for banned in ("eval(", "exec(", "__import__("):
            # Skip occurrences inside string literals meant as documentation.
            # Simplest: reject unless preceded by '#' on the same line.
            for i, line in enumerate(text.splitlines(), start=1):
                idx = line.find(banned)
                if idx < 0:
                    continue
                comment = line.find("#")
                in_string = line.count('"') + line.count("'")
                # Crude sanity: only fail if not in a comment AND not wrapped
                # in a string literal (very conservative — we have none at
                # all in our files, so this should never match).
                if (comment < 0 or idx < comment) and in_string == 0:
                    violations.append(f"{fname}:{i}: {line.strip()}")
    assert not violations, f"Banned calls detected: {violations}"
