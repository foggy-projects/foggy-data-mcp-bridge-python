"""``execute_plan`` — compile + execute a ``QueryPlan`` end-to-end.

This is the bridge between the M6 compiler (plan → SQL) and the Step 0
``SemanticQueryService.execute_sql`` (SQL → rows). It lives in
``runtime/`` because semantically it turns a plan into real data —
``compilation/`` only produces SQL.

Error routing (spec §错误模型规划)
-----------------------------------
* Upstream structured exceptions (``AuthorityResolutionError`` /
  ``ComposeSchemaError`` / ``ComposeCompileError``) are **not** wrapped
  — they propagate verbatim so MCP callers branch on ``phase`` /
  ``error_code``.
* Database-level failures from ``execute_sql`` (driver errors, broken
  connections, SQL-level errors) become ``RuntimeError`` with the
  ``"Plan execution failed at execute phase:"`` prefix. ``__cause__``
  is preserved so the full exception chain reaches logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..compilation.compiler import compile_plan_to_sql
from ..plan.plan import QueryPlan


__all__ = ["ComposeExecutionRows", "execute_plan", "pick_route_model"]


class ComposeExecutionRows(list):
    """Rows returned by a compose query, carrying optional SQL evidence.

    The class intentionally behaves like a plain list for script/runtime
    callers. MCP output layers may inspect the ``foggy_*`` attributes to
    expose execution evidence without changing the script-visible value.
    """

    def __init__(
        self,
        rows: List[Dict[str, Any]],
        *,
        sql: Optional[str] = None,
        params: Optional[List[Any]] = None,
        route_model: Optional[str] = None,
    ):
        super().__init__(rows)
        self.foggy_sql = sql
        self.foggy_params = list(params or [])
        self.foggy_route_model = route_model


def pick_route_model(plan: QueryPlan) -> Optional[str]:
    """Return the left-preorder first :class:`BaseModelPlan.model` under
    ``plan``. Used as the ``route_model`` hint for multi-datasource
    routing inside :meth:`SemanticQueryService.execute_sql`.

    Delegates to :meth:`QueryPlan.base_model_plans` which M2 guarantees
    on every concrete subclass (BaseModel / Derived / Union / Join) and
    whose contract is left-preorder traversal.
    """
    if plan is None:
        return None
    bases = plan.base_model_plans()
    return bases[0].model if bases else None


def execute_plan(
    plan: QueryPlan,
    ctx: Any,
    *,
    semantic_service: Any,
    dialect: str = "mysql",
) -> List[Dict[str, Any]]:
    """Compile ``plan`` to SQL via :func:`compile_plan_to_sql` and run it
    through :meth:`SemanticQueryService.execute_sql`.

    Parameters
    ----------
    plan:
        Any concrete :class:`QueryPlan` subclass.
    ctx:
        :class:`ComposeQueryContext`. Typed as ``Any`` to avoid circular
        imports.
    semantic_service:
        Must expose ``execute_sql(sql, params, *, route_model)``.
    dialect:
        Forwarded to the compiler. Default ``"mysql"``.

    Returns
    -------
    List[Dict[str, Any]]
        Row dicts. Empty list is a legal success (no rows matched).

    Raises
    ------
    AuthorityResolutionError / ComposeSchemaError / ComposeCompileError:
        Propagated verbatim from :func:`compile_plan_to_sql`.
    ComposeSandboxViolationError:
        Propagated if any upstream layer raises.
    RuntimeError:
        Database-level failures from ``execute_sql``. Message starts with
        ``"Plan execution failed at execute phase:"`` and ``__cause__``
        holds the original exception.
    """
    composed = compile_plan_to_sql(
        plan, ctx, semantic_service=semantic_service, dialect=dialect,
    )

    route_model = pick_route_model(plan)

    try:
        rows = semantic_service.execute_sql(
            composed.sql,
            composed.params,
            route_model=route_model,
        )
        return ComposeExecutionRows(
            list(rows or []),
            sql=composed.sql,
            params=list(composed.params or []),
            route_model=route_model,
        )
    except Exception as exc:
        # Execute-phase failures get a dedicated tag so the MCP layer
        # can surface ``phase: "execute"`` without inspecting the cause.
        raise RuntimeError(
            f"Plan execution failed at execute phase: {exc}"
        ) from exc
