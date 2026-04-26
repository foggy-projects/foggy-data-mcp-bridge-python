"""Script execution entry — ties ``QueryPlan`` nodes to real SQL execution.

``run_script`` parses a Compose Query script with the dialect that moves
``from`` out of the reserved-word list, evaluates it with fsscript, and
returns whatever the script produces (typically a row list from
``.execute()`` or a ``ComposedSql`` from ``.to_sql()``).

Key design decisions:

1. **Host infrastructure is invisible to the script.** ``semantic_service``
   / ``dialect`` / ``ComposeQueryContext`` ride on :data:`_compose_runtime`
   (a :class:`ContextVar`), NOT on the evaluator context. ``QueryPlan``
   methods read the bundle from the ContextVar when called.
2. **Evaluator visible surface is frozen.** ``module_loader`` and
   ``bean_registry`` are both ``None`` (no ``import '@bean'`` escape);
   we supplement the fsscript builtins with just ``from`` and ``dsl``
   (alias). The full allowed set is :data:`ALLOWED_SCRIPT_GLOBALS`.
3. **Nested scripts restore parent bundle.** ``_compose_runtime.set(...)``
   returns a token; ``reset(token)`` runs in a ``finally`` block.
   Each asyncio task inherits a Context copy, so concurrent scripts
   don't collide.
4. **Sandbox integrity: no Python ``eval`` / ``exec`` / ``__import__``**
   appears in this module or its helpers.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from foggy.fsscript.evaluator import ExpressionEvaluator
from foggy.fsscript.expressions.control_flow import ReturnException
from foggy.fsscript.parser import COMPOSE_QUERY_DIALECT, FsscriptParser

from .. import ComposedSql
from ..context.compose_query_context import ComposeQueryContext
from ..plan import from_ as _plan_from
from ..plan.plan import QueryPlan
from ..plan.query_factory import INSTANCE as _query_factory

from ..sandbox import (
    scan_script_source,
    validate_columns,
    validate_security_param,
    validate_slice,
)

from .plans_interceptor import intercept_plans

__all__ = [
    "ALLOWED_SCRIPT_GLOBALS",
    "ComposeRuntimeBundle",
    "ScriptResult",
    "current_bundle",
    "run_script",
    "set_bundle",
]


# ---------------------------------------------------------------------------
# Frozen bundle — carries host infra through the ContextVar.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComposeRuntimeBundle:
    """Per-script-invocation host infrastructure bundle.

    Stored in :data:`_compose_runtime`. ``QueryPlan.execute`` and
    ``QueryPlan.to_sql`` read it via :func:`current_bundle`; they never
    receive it as a direct argument from the script.

    Frozen so a nested script cannot mutate the parent's bundle. The
    ContextVar itself provides isolation via ``reset(token)``.

    Attributes
    ----------
    ctx:
        The :class:`ComposeQueryContext` for this invocation.
    semantic_service:
        Must expose ``execute_sql(sql, params, *, route_model)`` — the
        Step 0 public method added for M7.
    dialect:
        One of ``"mysql"`` / ``"mysql8"`` / ``"postgres"`` / ``"mssql"``
        / ``"sqlite"``. Forwarded to ``compile_plan_to_sql``.
    """

    ctx: ComposeQueryContext
    semantic_service: Any
    dialect: str = "mysql"


_compose_runtime: ContextVar[Optional[ComposeRuntimeBundle]] = ContextVar(
    "_compose_runtime", default=None
)


def current_bundle() -> Optional[ComposeRuntimeBundle]:
    """Return the ambient compose runtime bundle, or ``None`` when called
    outside :func:`run_script` (e.g. unit tests wiring ``plan.execute``
    manually without :func:`set_bundle`)."""
    return _compose_runtime.get()


def set_bundle(bundle: ComposeRuntimeBundle):
    """Install ``bundle`` on the ContextVar and return the reset token.

    Callers MUST use ``try/finally`` to reset the token — otherwise a
    nested script would not see its parent's bundle restored when it
    returns.
    """
    return _compose_runtime.set(bundle)


# ---------------------------------------------------------------------------
# Script result
# ---------------------------------------------------------------------------


@dataclass
class ScriptResult:
    """What :func:`run_script` returns.

    Attributes
    ----------
    value:
        Whatever the script's last expression / return value is.
        Typically ``List[Dict]`` (from ``.execute()``) or ``ComposedSql``
        (from ``.toSql()``).
    sql:
        Most-recent SQL string observed during plan execution — captured
        by the runtime so MCP callers can show it back to the LLM for
        debugging. ``None`` when no plan was executed.
    params:
        Bind parameters for :attr:`sql`. ``None`` when no plan was
        executed.
    warnings:
        Non-fatal warnings collected during execution. Reserved for
        future use (Layer B pre-checks / dialect fallback notices).
    """

    value: Any = None
    sql: Optional[str] = None
    params: Optional[List[Any]] = None
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Allowed evaluator surface
# ---------------------------------------------------------------------------

#: The frozen set of names the Compose Query script is allowed to see at the
#: top level. Family prefixes (``Array_*`` / ``Console_*``) are filtered out
#: by the lockdown test before comparing. ``from`` / ``dsl`` are the plan
#: constructors; the rest are fsscript builtins from ``_setup_builtins``.
#: If fsscript adds a new name, update this set AND the lockdown test.
ALLOWED_SCRIPT_GLOBALS: frozenset = frozenset({
    "JSON",
    "parseInt", "parseFloat", "toString",
    "String", "Number", "Boolean",
    "isNaN", "isFinite",
    "Array", "Object", "Function",
    "typeof",
    "from", "dsl", "Query",
    "params",
})


# ---------------------------------------------------------------------------
# Script execution entry
# ---------------------------------------------------------------------------


def _from_dsl(options: Dict[str, Any], *args):
    """Adapter from the script-world ``from(options)`` call → the Python
    plan factory ``from_(...)``.

    Accepts a single dict argument (matching the spec examples' shape) and
    forwards keyword-style. Also accepts keyword arguments for callers
    that prefer ``from_(model="M")``.
    """
    if isinstance(options, dict):
        validate_security_param(options, "script-eval")
        validate_columns(options.get("columns"), "script-eval")
        validate_slice(options.get("slice"), "script-eval")
        kwargs = {}
        for k, v in options.items():
            if k == "groupBy":
                kwargs["group_by"] = v
            elif k == "orderBy":
                kwargs["order_by"] = v
            else:
                kwargs[k] = v
                
        # If columns is missing, add it as None so we don't get TypeError
        if "columns" not in kwargs:
            kwargs["columns"] = None
            
        return _plan_from(**kwargs)
    # fall back — if the caller passes a plan + option dict, forward
    # literally
    return _plan_from(options, *args)


def run_script(
    script: str,
    ctx: ComposeQueryContext,
    *,
    semantic_service: Any,
    dialect: str = "mysql",
    preview_mode: bool = False,
) -> ScriptResult:
    """Execute ``script`` under a fresh compose runtime bundle.

    Parameters
    ----------
    script:
        The fsscript source. May be empty / whitespace (returns
        ``ScriptResult(value=None)``). Parsed with
        :data:`COMPOSE_QUERY_DIALECT` so ``from`` is usable as a function
        call identifier.
    ctx:
        Compose query context (principal + authority resolver + namespace).
    semantic_service:
        Must expose ``execute_sql(sql, params, *, route_model)``.
    dialect:
        SQL dialect forwarded to the compiler. Default ``"mysql"``.
    preview_mode:
        When ``True``, any :class:`QueryPlan` returned in the result
        envelope (under ``plans``) — or returned bare — is converted to
        :class:`ComposedSql` via ``.to_sql()`` instead of being executed.
        Used by the controller's ``preview`` parameter to surface the SQL
        for human review before committing to a database round-trip.
        Default ``False`` (execute normally).

    Returns
    -------
    ScriptResult

    Notes
    -----
    The post-script processing (``plans`` interception) follows the
    contract documented in :mod:`plans_interceptor`. Three return shapes
    are recognised:

    1. ``{ "plans": <plans>, ... }`` — named/list/single plan envelope.
       Each plan is auto-executed (or previewed) and the dict is rebuilt
       with the evaluated values in place of the plans.
    2. Bare :class:`QueryPlan` — backward-compat from the M7 baseline.
       Auto-executed (or previewed).
    3. Anything else — passed through unchanged.

    Raises
    ------
    ValueError
        On ``ctx is None`` / ``semantic_service is None``.
    AuthorityResolutionError / ComposeSchemaError / ComposeCompileError /
    ComposeSandboxViolationError / RuntimeError:
        Propagated verbatim from upstream. M7 does not introduce new
        error-code families.
    """
    if ctx is None:
        raise ValueError("run_script: ctx is required")
    if semantic_service is None:
        raise ValueError("run_script: semantic_service is required")

    source = script if script is not None else ""
    if not source.strip():
        return ScriptResult(value=None)

    bundle = ComposeRuntimeBundle(
        ctx=ctx, semantic_service=semantic_service, dialect=dialect,
    )
    token = set_bundle(bundle)
    try:
        # Layer A & C static scan
        scan_script_source(source)

        # Parse with the compose dialect — removes `from` from reserved words.
        parser = FsscriptParser(source, dialect=COMPOSE_QUERY_DIALECT)
        program = parser.parse_program()

        # Evaluator: NO module loader, NO bean registry. This disables
        # ``import 'x'`` and ``import '@bean'`` — the two paths that
        # could reach arbitrary Python or bean-registered objects.
        evaluator = ExpressionEvaluator(
            context={},
            module_loader=None,
            bean_registry=None,
        )
        # Supplement: compose-query plan constructor + alias.
        evaluator.context["from"] = _from_dsl
        evaluator.context["dsl"] = _from_dsl
        # OO entry point: Query.from("ModelName")
        evaluator.context["Query"] = _query_factory
        # Inject read-only business params
        if ctx.params:
            evaluator.context["params"] = dict(ctx.params)
        else:
            evaluator.context["params"] = {}

        try:
            raw_value = evaluator.evaluate(program)
        except ReturnException as ret_exc:
            # Top-level `return expr;` lifts out of the program scope.
            raw_value = getattr(ret_exc, "value", None)

        # Plans interception — Phase 4 contract. This MUST run inside the
        # ``try/finally`` block while the runtime bundle is still active,
        # because ``QueryPlan.execute()`` and ``QueryPlan.to_sql()`` read
        # the bundle from the ContextVar.
        value = intercept_plans(raw_value, preview_mode=preview_mode)

        # Best-effort SQL/params capture — only when the value reduces
        # to a single ComposedSql. With the new ``plans`` envelope the
        # value is typically a dict (preview mode) or a list (rows), so
        # these stay None except in the legacy single-plan path.
        result_sql = None
        result_params = None
        if isinstance(value, ComposedSql):
            result_sql = value.sql
            result_params = list(value.params)
        return ScriptResult(
            value=value, sql=result_sql, params=result_params,
        )
    finally:
        _compose_runtime.reset(token)
