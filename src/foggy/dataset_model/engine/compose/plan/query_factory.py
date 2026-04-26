"""``QueryFactory`` — global ``Query`` object for the fsscript sandbox.

Injected as ``evaluator.context["Query"]`` so scripts can write::

    const sales = Query.from("OdooSaleOrderModel");

The Python fsscript interpreter dispatches ``Query.from(...)`` via
``getattr(QueryFactory_instance, "from")``. Since ``from`` is a Python
reserved word, we intercept it via ``__getattr__`` and route to
``_from_impl``.

Cross-repo invariant: mirrors Java
``com.foggyframework.dataset.db.model.engine.compose.plan.QueryFactory``.

.. versionadded:: 8.2.0.beta
"""

from __future__ import annotations

from typing import Any

from .plan import BaseModelPlan


class QueryFactory:
    """Global ``Query`` object for fsscript sandbox.

    The only supported method is ``from(modelName)`` — which in Python
    is dispatched via ``__getattr__`` because ``from`` is a reserved word.
    """

    def __getattr__(self, name: str) -> Any:
        # fsscript calls Query.from(...) → getattr(self, "from")
        # We return a bound method so the evaluator can call it.
        if name == "from":
            return self._from_impl
        raise AttributeError(
            f"Query does not support attribute: {name}. Available: from(modelName)"
        )

    def _from_impl(self, model_name: str) -> BaseModelPlan:
        """Create a ``BaseModelPlan`` with just the model name.

        Columns are specified later via ``.select()``.
        """
        if not model_name or not isinstance(model_name, str):
            raise ValueError(
                "Query.from() requires exactly 1 argument: "
                "a non-empty model name string"
            )
        return BaseModelPlan(model=model_name, columns=())

    def __repr__(self) -> str:
        return "Query"


#: Singleton instance — no state, can be shared across scripts.
INSTANCE = QueryFactory()
