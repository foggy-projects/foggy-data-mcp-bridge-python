"""QueryFacade pipeline - step-based query execution.

Aligned with Java QueryFacade + DataSetResultStep.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from foggy.dataset_model.semantic.inline_expression import parse_inline_aggregate


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class ModelResultContext:
    """Mutable context bag passed through the query pipeline."""

    model_name: str
    request: Dict[str, Any]  # The query request (columns, slice, orderBy, etc.)
    query_model: Any  # DbTableModelImpl
    sql: Optional[str] = None
    params: List[Any] = field(default_factory=list)
    result: Optional[Any] = None  # Query result data
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    ext_data: Dict[str, Any] = field(default_factory=dict)
    aborted: bool = False


# ---------------------------------------------------------------------------
# Step ABC
# ---------------------------------------------------------------------------

class QueryStep(ABC):
    """Base class for query pipeline steps."""

    @property
    def order(self) -> int:
        """Step execution order (lower = earlier)."""
        return 100

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def before_query(self, context: ModelResultContext) -> bool:
        """Called before query execution.  Return ``False`` to abort pipeline."""
        return True

    def after_query(self, context: ModelResultContext) -> bool:
        """Called after query execution (process step).  Return ``False`` to abort."""
        return True


# ---------------------------------------------------------------------------
# Concrete steps
# ---------------------------------------------------------------------------

class QueryRequestValidationStep(QueryStep):
    """Validate that all referenced columns exist in the model (order=0).

    Adds warnings for unknown fields but does **not** abort the pipeline.
    """

    @property
    def order(self) -> int:
        return 0

    def before_query(self, context: ModelResultContext) -> bool:
        columns = context.request.get("columns") or []
        model = context.query_model
        for col_name in columns:
            resolved = model.resolve_field(col_name)
            if resolved is None:
                context.warnings.append(f"Unknown field: {col_name}")
        return True  # never abort


class InlineExpressionStep(QueryStep):
    """Detect inline aggregation expressions in column list (order=5).

    Expressions like ``sum(amount) as total`` are parsed and stored in
    ``context.ext_data['parsed_inline_expressions']``.
    """

    @property
    def order(self) -> int:
        return 5

    def before_query(self, context: ModelResultContext) -> bool:
        columns = context.request.get("columns") or []
        parsed: List[Dict[str, Any]] = []
        for col_name in columns:
            parsed_expr = parse_inline_aggregate(col_name)
            if parsed_expr:
                func_name = parsed_expr.function
                field_name = parsed_expr.inner_expression
                parsed.append({
                    "original": col_name,
                    "function": func_name,
                    "field": field_name,
                    "alias": parsed_expr.alias,
                })
        context.ext_data["parsed_inline_expressions"] = parsed
        return True


class AutoGroupByStep(QueryStep):
    """Auto-generate ``groupBy`` from non-aggregated columns (order=10).

    If the request has aggregated columns (measures) but no explicit
    ``groupBy``, the step infers one from the non-aggregated columns.
    """

    @property
    def order(self) -> int:
        return 10

    def before_query(self, context: ModelResultContext) -> bool:
        request = context.request
        # Skip if explicit groupBy already set
        if request.get("groupBy"):
            return True

        columns = context.request.get("columns") or []
        model = context.query_model

        # Collect inline expression originals so we can skip them
        inline_exprs = context.ext_data.get("parsed_inline_expressions") or []
        inline_originals: set = {e["original"] for e in inline_exprs}

        dims: List[str] = []
        has_measure = False
        for col_name in columns:
            if col_name in inline_originals:
                has_measure = True
                continue
            resolved = model.resolve_field(col_name)
            if resolved is not None and resolved.get("is_measure"):
                has_measure = True
            else:
                # Treat unresolved and non-measure columns as dimension-like
                dims.append(col_name)

        if inline_exprs:
            has_measure = True

        if has_measure and dims:
            context.ext_data["auto_group_by"] = dims
            request["groupBy"] = dims

        return True


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------

class QueryFacade:
    """Orchestrates query execution through a step pipeline.

    Aligned with Java ``QueryFacadeImpl``.
    """

    def __init__(self, steps: Optional[List[QueryStep]] = None):
        self._steps: List[QueryStep] = sorted(
            steps if steps is not None else self._default_steps(),
            key=lambda s: s.order,
        )

    @staticmethod
    def _default_steps() -> List[QueryStep]:
        return [
            QueryRequestValidationStep(),
            InlineExpressionStep(),
            AutoGroupByStep(),
        ]

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def execute(
        self,
        context: ModelResultContext,
        query_fn: Optional[Callable[[ModelResultContext], None]] = None,
    ) -> ModelResultContext:
        """Execute the full pipeline: beforeQuery -> query -> afterQuery.

        Args:
            context: Query context.
            query_fn: Callable(context) -> None that executes the actual
                      query and populates ``context.result``.
        """
        # beforeQuery pipeline
        for step in self._steps:
            if not step.before_query(context):
                context.aborted = True
                return context

        # Execute query
        if query_fn and not context.aborted:
            query_fn(context)

        # afterQuery pipeline
        for step in self._steps:
            if not step.after_query(context):
                break

        return context

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_step(self, step: QueryStep) -> None:
        self._steps.append(step)
        self._steps.sort(key=lambda s: s.order)

    @property
    def steps(self) -> List[QueryStep]:
        """Read-only view of registered steps (sorted)."""
        return list(self._steps)
