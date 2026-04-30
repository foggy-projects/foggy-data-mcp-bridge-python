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
from ..capability.policy import CapabilityPolicy
from ..capability.registry import CapabilityRegistry
from ..capability.runtime_integration import build_capability_context
from ..capability.library_loader import ControlledLibraryModuleLoader
from ..context.compose_query_context import ComposeQueryContext
from ..plan import from_ as _plan_from
from ..plan.column_normalizer import normalize_columns as _normalize_columns
from ..plan.plan import QueryPlan
from ..plan.query_factory import INSTANCE as _query_factory

from ..sandbox import (
    scan_script_source,
    validate_columns,
    validate_security_param,
    validate_slice,
)

from .plans_interceptor import intercept_plans

# v1.9 P2.2: run context propagation and suspension manager.
from .pause_primitive import set_run_context, _script_run_context
from .suspension import ScriptRunContext
from .suspension_manager import SuspensionManager

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

#: v1.9 P2.2: module-level default SuspensionManager shared by all
#: ``run_script`` invocations.  Callers that need a custom manager
#: (e.g. tests) can pass ``suspension_manager`` to ``run_script``.
_default_suspension_manager = SuspensionManager()


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
        Post-interception script return value. Common shapes:

        * ``dict`` — the ``{ plans, metadata, ... }`` envelope, with each
          plan inside ``plans`` already replaced by rows or
          :class:`ComposedSql` (depending on ``preview_mode``).
        * ``List[Dict]`` — rows from a script that called ``.execute()``
          directly and returned the result (no envelope).
        * :class:`ComposedSql` — SQL preview from a direct ``.to_sql()``
          call (no envelope).
        * Bare :class:`QueryPlan` — script returned the AST verbatim
          (Python-specific; see :mod:`plans_interceptor`).
        * Any other literal — passed through.
    sql:
        Convenience capture for the legacy "single :class:`ComposedSql`
        return" path. ``None`` in envelope mode (callers should walk
        ``value["plans"]`` instead).
    params:
        Bind parameters for :attr:`sql`. ``None`` when :attr:`sql` is.
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

        # G5 Phase 1 (F4): normalize {field, agg?, as?} dict entries in
        # `columns` to their canonical string form BEFORE validate_columns
        # (which still expects strings / heterogeneous list).
        raw_columns = options.get("columns")
        if raw_columns is not None:
            options = dict(options)  # shallow copy — don't mutate caller's dict
            options["columns"] = _normalize_columns(raw_columns)

        validate_columns(options.get("columns"), "script-eval")
        validate_slice(options.get("slice"), "script-eval")
        kwargs = {}
        for k, v in options.items():
            if k == "groupBy":
                kwargs["group_by"] = v
            elif k == "orderBy":
                kwargs["order_by"] = v
            elif k == "calculatedFields":
                kwargs["calculated_fields"] = v
            else:
                kwargs[k] = v

        # If columns is missing, add it as None so we don't get TypeError
        if "columns" not in kwargs:
            kwargs["columns"] = None

        return _plan_from(**kwargs)
    # fall back — if the caller passes a plan + option dict, forward
    # literally
    return _plan_from(options, *args)


def _evaluate_program(
    script: str,
    ctx: ComposeQueryContext,
    *,
    capability_registry: Optional[CapabilityRegistry] = None,
    capability_policy: Optional[CapabilityPolicy] = None,
    library_registry: Optional[CapabilityRegistry] = None,
    library_policy: Optional[CapabilityPolicy] = None,
) -> Any:
    """Run sandbox scan + parse + evaluate for ``script``.

    Caller is responsible for pushing a :class:`ComposeRuntimeBundle`
    onto :data:`_compose_runtime` BEFORE calling — this helper does not
    manage bundle lifecycle so callers can keep the same bundle live
    across both evaluation and post-processing (e.g. interception).

    Returns the evaluator's return value, or ``None`` for empty /
    whitespace input. Top-level ``return expr;`` is unwrapped from
    :class:`ReturnException` automatically.

    Upstream errors (sandbox / parse / authority) propagate verbatim.
    """
    source = script if script is not None else ""
    if not source.strip():
        return None

    # Layer A & C static scan.
    allow_controlled_imports = (
        library_registry is not None and library_policy is not None
    )
    scan_script_source(
        source,
        allow_controlled_imports=allow_controlled_imports,
    )

    parser = FsscriptParser(source, dialect=COMPOSE_QUERY_DIALECT)
    program = parser.parse_program()

    module_loader = None
    if allow_controlled_imports:
        module_loader = ControlledLibraryModuleLoader(
            library_registry,
            library_policy,
            surface="compose_runtime",
        )

    # Evaluator with NO bean registry.  Module loader stays None by default;
    # v1.8 only supplies a registry-backed loader when the caller explicitly
    # provides library_registry + library_policy.
    evaluator = ExpressionEvaluator(
        context={},
        module_loader=module_loader,
        bean_registry=None,
    )
    evaluator.context["from"] = _from_dsl
    evaluator.context["dsl"] = _from_dsl
    evaluator.context["Query"] = _query_factory
    evaluator.context["params"] = (
        dict(ctx.params) if ctx.params else {}
    )

    # v1.7: inject capability-authorized entries.
    # Default-empty: no registry/policy → no capability entries.
    cap_ctx = build_capability_context(capability_registry, capability_policy)
    evaluator.context.update(cap_ctx)

    try:
        return evaluator.evaluate(program)
    except ReturnException as ret_exc:
        # Top-level `return expr;` lifts out of the program scope.
        return getattr(ret_exc, "value", None)


def _run_script_no_intercept(
    script: str,
    ctx: ComposeQueryContext,
    *,
    semantic_service: Any,
    dialect: str = "mysql",
    capability_registry: Optional[CapabilityRegistry] = None,
    capability_policy: Optional[CapabilityPolicy] = None,
    library_registry: Optional[CapabilityRegistry] = None,
    library_policy: Optional[CapabilityPolicy] = None,
    suspension_manager: Optional[SuspensionManager] = None,
) -> Any:
    """Public-but-underscored entry: run ``script`` under a fresh
    :class:`ComposeRuntimeBundle` and return the raw evaluator value
    BEFORE :func:`plans_interceptor.intercept_plans` runs.

    Used by tests that need to assert on the literal ``{ plans,
    metadata }`` envelope the script returned (with plans still as
    :class:`QueryPlan` instances). Production code should call
    :func:`run_script` so post-processing happens.

    Empty / whitespace input returns ``None``. Required-parameter
    validation matches :func:`run_script`.
    """
    if ctx is None:
        raise ValueError("run_script: ctx is required")
    if semantic_service is None:
        raise ValueError("run_script: semantic_service is required")

    bundle = ComposeRuntimeBundle(
        ctx=ctx, semantic_service=semantic_service, dialect=dialect,
    )
    token = set_bundle(bundle)

    # v1.9 P2.2: push run context onto ContextVar.
    mgr = suspension_manager or _default_suspension_manager
    run_ctx = ScriptRunContext()
    run_ctx._manager = mgr  # type: ignore[attr-defined]
    mgr.register_run(run_ctx)
    run_token = set_run_context(run_ctx)

    try:
        return _evaluate_program(
            script, ctx,
            capability_registry=capability_registry,
            capability_policy=capability_policy,
            library_registry=library_registry,
            library_policy=library_policy,
        )
    finally:
        _script_run_context.reset(run_token)
        _compose_runtime.reset(token)
        # Complete the run if still running (not suspended/aborted).
        if not run_ctx.is_terminal and run_ctx.state.value == "RUNNING":
            try:
                mgr.complete_run(run_ctx.run_id)
            except Exception:
                pass


def run_script(
    script: str,
    ctx: ComposeQueryContext,
    *,
    semantic_service: Any,
    dialect: str = "mysql",
    preview_mode: bool = False,
    capability_registry: Optional[CapabilityRegistry] = None,
    capability_policy: Optional[CapabilityPolicy] = None,
    library_registry: Optional[CapabilityRegistry] = None,
    library_policy: Optional[CapabilityPolicy] = None,
    suspension_manager: Optional[SuspensionManager] = None,
) -> ScriptResult:
    """Execute ``script`` and return a :class:`ScriptResult` with plans
    inside any ``{ plans, ... }`` envelope auto-evaluated.

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
        When ``True``, plans inside the envelope's ``plans`` field are
        converted to :class:`ComposedSql` via ``.to_sql()`` instead of
        being executed against the database. Used by the controller's
        ``preview`` parameter to surface SQL for human review.
    capability_registry:
        Optional :class:`CapabilityRegistry` with registered functions
        and object facades. Default ``None`` → no capability injection.
    capability_policy:
        Optional :class:`CapabilityPolicy` controlling which registered
        capabilities are visible.  Default ``None`` → no capability
        injection.
    library_registry:
        Optional registry containing controlled fsscript libraries.
        Default ``None`` keeps import disabled at Layer A.
    library_policy:
        Optional policy controlling visible libraries / symbols.
        Must be provided together with ``library_registry`` to enable
        controlled imports.
    suspension_manager:
        Optional :class:`SuspensionManager`.  Default ``None`` uses the
        module-level default manager.

    Notes
    -----
    Post-script processing follows :mod:`plans_interceptor`:

    1. ``{ "plans": <plans>, ... }`` — each :class:`QueryPlan` inside
       ``plans`` (dict / list / single) is auto-executed (or previewed).
    2. Bare :class:`QueryPlan` — passes through verbatim. Python-specific
       divergence from Java that preserves the M7 unit-test contract for
       AST assertions; production callers always wrap in the envelope.
    3. Anything else — passed through unchanged.

    Raises
    ------
    ValueError
        On ``ctx is None`` / ``semantic_service is None``.
    AuthorityResolutionError / ComposeSchemaError / ComposeCompileError /
    ComposeSandboxViolationError / CapabilityError / RuntimeError:
        Propagated verbatim from upstream.
    ScriptSuspendRejectedError / ScriptSuspendTimeoutError:
        If a handler calls ``compose_pause`` and the pause is rejected
        or times out.
    """
    if ctx is None:
        raise ValueError("run_script: ctx is required")
    if semantic_service is None:
        raise ValueError("run_script: semantic_service is required")

    # Single bundle covers both evaluation AND interception —
    # ``QueryPlan.execute() / .to_sql()`` reads the bundle from the
    # ContextVar, so it must stay live until ``intercept_plans``
    # finishes processing every plan.
    bundle = ComposeRuntimeBundle(
        ctx=ctx, semantic_service=semantic_service, dialect=dialect,
    )
    token = set_bundle(bundle)

    # v1.9 P2.2: push run context onto ContextVar.
    mgr = suspension_manager or _default_suspension_manager
    run_ctx = ScriptRunContext()
    run_ctx._manager = mgr  # type: ignore[attr-defined]
    mgr.register_run(run_ctx)
    run_token = set_run_context(run_ctx)

    try:
        raw_value = _evaluate_program(
            script, ctx,
            capability_registry=capability_registry,
            capability_policy=capability_policy,
            library_registry=library_registry,
            library_policy=library_policy,
        )
        value = intercept_plans(raw_value, preview_mode=preview_mode)
    finally:
        _script_run_context.reset(run_token)
        _compose_runtime.reset(token)
        # Complete the run if still running.
        if not run_ctx.is_terminal and run_ctx.state.value == "RUNNING":
            try:
                mgr.complete_run(run_ctx.run_id)
            except Exception:
                pass

    # Lift sql/params for the legacy single-ComposedSql return path.
    # Envelope mode keeps these None — callers walk ``value["plans"]``.
    result_sql = None
    result_params = None
    if isinstance(value, ComposedSql):
        result_sql = value.sql
        result_params = list(value.params)
    return ScriptResult(
        value=value, sql=result_sql, params=result_params,
    )
