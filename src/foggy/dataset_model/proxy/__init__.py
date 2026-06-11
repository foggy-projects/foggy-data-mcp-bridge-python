"""TableModelProxy — dynamic field access for QM definitions.

Aligned with Java TableModelProxy + DimensionProxy + ColumnRef.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class ColumnRef:
    """Reference to a field on a table model.

    Examples:
        ColumnRef("FactSales", "orderId")              -> simple column
        ColumnRef("FactSales", "customer$memberLevel")  -> dimension property
        ColumnRef("FactSales", "product.category$id")   -> nested dimension
    """

    model_name: str
    field_ref: str
    alias: Optional[str] = None

    @property
    def is_dimension_ref(self) -> bool:
        return "$" in self.field_ref

    @property
    def is_nested(self) -> bool:
        return "." in self.field_ref.split("$")[0]

    @property
    def dimension_name(self) -> Optional[str]:
        if "$" in self.field_ref:
            return self.field_ref.split("$")[0]
        return None

    @property
    def property_name(self) -> Optional[str]:
        if "$" in self.field_ref:
            return self.field_ref.split("$")[1]
        return None


@dataclass(frozen=True)
class JoinConditionRef:
    """Single ON condition between two semantic fields."""

    left_model_name: str
    left_field_ref: str
    right_model_name: str
    right_field_ref: str


class DimensionProxy:
    """Enables chained dimension access: proxy.product.category$id

    Acts as intermediate in path traversal for nested dimensions.
    """

    def __init__(self, model_proxy: TableModelProxy, path_segments: List[str]):
        self._model_proxy = model_proxy
        self._path_segments = path_segments

    def __getattr__(self, name: str) -> ColumnRef | DimensionProxy:
        if name.startswith("_"):
            raise AttributeError(name)

        if "$" in name:
            # End of chain: product.category$id
            dim_name, prop = name.split("$", 1)
            full_path = ".".join(self._path_segments + [dim_name])
            return ColumnRef(self._model_proxy.model_name, f"{full_path}${prop}")
        # Continue chain: product.category -> DimensionProxy(["product", "category"])
        return DimensionProxy(self._model_proxy, self._path_segments + [name])

    @property
    def _field_ref(self) -> str:
        return ".".join(self._path_segments)

    @property
    def field_ref(self) -> str:
        return self._field_ref

    @property
    def model_name(self) -> str:
        return self._model_proxy.model_name

    def __repr__(self) -> str:
        return (
            f"DimensionProxy({self._model_proxy.model_name!r}, "
            f"path={self._path_segments!r})"
        )


@dataclass
class JoinBuilder:
    """Represents a pending JOIN operation between two models.

    Usage: fo.left_join(fp).on("orderId", "orderId")
    """

    left: TableModelProxy
    right: TableModelProxy
    join_type: str = "LEFT"
    on_left_key: Optional[str] = None
    on_right_key: Optional[str] = None
    conditions: List[JoinConditionRef] = None

    def __post_init__(self) -> None:
        if self.conditions is None:
            self.conditions = []

    @staticmethod
    def _normalize_ref(ref, model: TableModelProxy) -> Tuple[str, str]:
        if isinstance(ref, ColumnRef):
            return ref.model_name, ref.field_ref
        if isinstance(ref, DimensionProxy):
            return ref.model_name, ref.field_ref
        return model.model_name, ref

    def _append_condition(
        self,
        left_ref: ColumnRef | str,
        right_ref: ColumnRef | str,
    ) -> None:
        left_model_name, left_field_ref = self._normalize_ref(left_ref, self.left)
        right_model_name, right_field_ref = self._normalize_ref(right_ref, self.right)
        self.conditions.append(
            JoinConditionRef(
                left_model_name=left_model_name,
                left_field_ref=left_field_ref,
                right_model_name=right_model_name,
                right_field_ref=right_field_ref,
            )
        )
        self.on_left_key = left_field_ref
        self.on_right_key = right_field_ref

    def on(self, left_ref, right_ref) -> JoinBuilder:
        """Set JOIN condition.

        Args can be ColumnRef or string field names.
        """
        self.conditions = []
        self._append_condition(left_ref, right_ref)
        return self

    def and_(self, left_ref, right_ref) -> JoinBuilder:
        """Append an additional AND condition."""
        self._append_condition(left_ref, right_ref)
        return self

    def and__(self, left_ref, right_ref) -> JoinBuilder:
        """Compatibility helper for attribute names that cannot use a keyword."""
        return self.and_(left_ref, right_ref)

    def and_join(self, left_ref, right_ref) -> JoinBuilder:
        """Explicit alias for chained ON conditions."""
        return self.and_(left_ref, right_ref)

    def andClause(self, left_ref, right_ref) -> JoinBuilder:
        """CamelCase compatibility alias."""
        return self.and_(left_ref, right_ref)

    def __getattr__(self, name: str):
        if name == "and":
            return self.and_
        raise AttributeError(name)

    @property
    def on_conditions(self) -> List[JoinConditionRef]:
        return list(self.conditions)

    def get_condition_pairs(self) -> List[Tuple[str, str]]:
        return [(c.left_field_ref, c.right_field_ref) for c in self.conditions]

    def get_model_condition_pairs(self) -> List[JoinConditionRef]:
        return list(self.conditions)

    def has_conditions(self) -> bool:
        return bool(self.conditions)

    def primary_condition(self) -> Optional[JoinConditionRef]:
        if self.conditions:
            return self.conditions[0]
        return None

    def clone(self) -> JoinBuilder:
        cloned = JoinBuilder(self.left, self.right, self.join_type)
        cloned.conditions = list(self.conditions)
        cloned.on_left_key = self.on_left_key
        cloned.on_right_key = self.on_right_key
        return cloned

    def __iter__(self):
        return iter(self.conditions)

    def __len__(self) -> int:
        return len(self.conditions)

    def __bool__(self) -> bool:
        return bool(self.conditions)

    def __repr__(self) -> str:
        return (
            f"JoinBuilder(left={self.left!r}, right={self.right!r}, "
            f"join_type={self.join_type!r}, conditions={self.conditions!r})"
        )

    def andAlso(self, left_ref, right_ref) -> JoinBuilder:
        """Legacy-friendly alias."""
        return self.and_(left_ref, right_ref)

    def andThen(self, left_ref, right_ref) -> JoinBuilder:
        """Legacy-friendly alias."""
        return self.and_(left_ref, right_ref)

    def and_condition(self, left_ref, right_ref) -> JoinBuilder:
        """Snake-case alias."""
        return self.and_(left_ref, right_ref)

    def add_condition(self, left_ref, right_ref) -> JoinBuilder:
        """Low-level alias."""
        return self.and_(left_ref, right_ref)

    def on_many(self, *pairs: Tuple[object, object]) -> JoinBuilder:
        """Set multiple ON conditions at once."""
        self.conditions = []
        for left_ref, right_ref in pairs:
            self._append_condition(left_ref, right_ref)
        return self


class UnsupportedAggregateRelationProxy:
    """Carrier for Java aggregate relation DSL not implemented in Python yet.

    The object deliberately keeps ``aggregate_join_unsupported=True`` so the
    loader/compiler continue to fail closed while tests and future loader work
    can inspect the captured aggregate relation contract.
    """

    aggregate_join_unsupported = True

    def __init__(
        self,
        model_name: str,
        alias: Optional[str] = None,
        filters: Optional[List[dict]] = None,
        group_by: Optional[List[dict]] = None,
        measures: Optional[List[dict]] = None,
    ):
        self._model_name = model_name
        self._alias = alias
        self._filters = list(filters or [])
        self._group_by = list(group_by or [])
        self._measures = list(measures or [])

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def alias(self) -> Optional[str]:
        return self._alias

    @property
    def filters(self) -> List[dict]:
        return list(self._filters)

    @property
    def group_by(self) -> List[dict]:
        return list(self._group_by)

    @property
    def measures(self) -> List[dict]:
        return list(self._measures)

    @staticmethod
    def _normalize_ref(ref: Any, default_model_name: str) -> Tuple[str, str]:
        if isinstance(ref, ColumnRef):
            return ref.model_name, ref.field_ref
        if isinstance(ref, DimensionProxy):
            return ref.model_name, ref.field_ref
        return default_model_name, str(ref)

    def _clone(self, alias: Optional[str] = None) -> UnsupportedAggregateRelationProxy:
        return UnsupportedAggregateRelationProxy(
            self._model_name,
            alias=self._alias if alias is None else alias,
            filters=self._filters,
            group_by=self._group_by,
            measures=self._measures,
        )

    def _append_filter(self, op: str, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        if not args:
            return self
        model_name, field_ref = self._normalize_ref(args[0], self._model_name)
        value = kwargs.get("value")
        if len(args) > 1:
            value = args[1]
        self._filters.append(
            {
                "model": model_name,
                "field": field_ref,
                "op": op,
                "value": value,
            }
        )
        return self

    def filterEq(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter("=", *args, **kwargs)

    def filterIn(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter("IN", *args, **kwargs)

    def filterGt(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter(">", *args, **kwargs)

    def filterGte(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter(">=", *args, **kwargs)

    def filterLt(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter("<", *args, **kwargs)

    def filterLte(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_filter("<=", *args, **kwargs)

    def groupBy(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        for ref in args:
            model_name, field_ref = self._normalize_ref(ref, self._model_name)
            self._group_by.append({"model": model_name, "field": field_ref})
        return self

    def _append_measure(
        self,
        aggregation: str,
        *args,
        distinct: bool = False,
        **kwargs,
    ) -> UnsupportedAggregateRelationProxy:
        field_ref: Optional[str] = None
        model_name: Optional[str] = None
        if args:
            model_name, field_ref = self._normalize_ref(args[0], self._model_name)
        alias = kwargs.get("alias") or kwargs.get("name")
        if len(args) > 1 and isinstance(args[1], str):
            alias = args[1]
        if alias is None:
            alias = field_ref or aggregation.lower()
        self._measures.append(
            {
                "aggregation": aggregation,
                "field": field_ref,
                "model": model_name,
                "alias": alias,
                "distinct": distinct,
            }
        )
        return self

    def sum(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("SUM", *args, **kwargs)

    def avg(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("AVG", *args, **kwargs)

    def min(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("MIN", *args, **kwargs)

    def max(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("MAX", *args, **kwargs)

    def count(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("COUNT", *args, **kwargs)

    def countDistinct(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return self._append_measure("COUNT_DISTINCT", *args, distinct=True, **kwargs)

    def as_(self, alias: str) -> UnsupportedAggregateRelationProxy:
        return self._clone(alias=alias)

    def to_carrier(self):
        from foggy.dataset_model.impl.model import (
            AggregateRelationDef,
            AggregateRelationFilterDef,
            AggregateRelationMeasureDef,
        )

        return AggregateRelationDef(
            right_model=self._model_name,
            alias=self._alias,
            group_by=[item["field"] for item in self._group_by],
            filters=[
                AggregateRelationFilterDef(
                    model=item["model"],
                    field=item["field"],
                    op=item["op"],
                    value=item.get("value"),
                )
                for item in self._filters
            ],
            measures=[
                AggregateRelationMeasureDef(
                    aggregation=item["aggregation"],
                    field=item.get("field"),
                    model=item.get("model"),
                    alias=item["alias"],
                    distinct=item.get("distinct", False),
                )
                for item in self._measures
            ],
        )

    def __getattr__(self, name: str):
        if name == "as":
            return self.as_
        if name.startswith("_"):
            raise AttributeError(name)
        return ColumnRef(self._model_name, name)


class UnsupportedAggregateJoinBuilder(UnsupportedAggregateRelationProxy):
    """Sentinel for Java leftJoinAggregate(...) declarations."""

    def __init__(self, left: TableModelProxy, right: TableModelProxy):
        super().__init__(right.model_name)
        self.left = left
        self.right = right
        self.join_type = "LEFT"
        self.conditions: List[JoinConditionRef] = []

    @property
    def on_conditions(self) -> List[JoinConditionRef]:
        return list(self.conditions)

    def _clone(self, alias: Optional[str] = None) -> UnsupportedAggregateJoinBuilder:
        cloned = UnsupportedAggregateJoinBuilder(self.left, self.right)
        cloned._alias = self.alias if alias is None else alias
        cloned._filters = list(self._filters)
        cloned._group_by = list(self._group_by)
        cloned._measures = list(self._measures)
        cloned.conditions = list(self.conditions)
        return cloned

    def _append_condition(self, left_ref: Any, right_ref: Any) -> None:
        left_model_name, left_field_ref = self._normalize_ref(left_ref, self.left.model_name)
        right_model_name, right_field_ref = self._normalize_ref(right_ref, self.right.model_name)
        self.conditions.append(
            JoinConditionRef(
                left_model_name=left_model_name,
                left_field_ref=left_field_ref,
                right_model_name=right_model_name,
                right_field_ref=right_field_ref,
            )
        )

    def on(self, left_ref, right_ref) -> UnsupportedAggregateJoinBuilder:
        self.conditions = []
        self._append_condition(left_ref, right_ref)
        return self

    def and_(self, left_ref, right_ref) -> UnsupportedAggregateJoinBuilder:
        self._append_condition(left_ref, right_ref)
        return self

    def andAlso(self, left_ref, right_ref) -> UnsupportedAggregateJoinBuilder:
        return self.and_(left_ref, right_ref)

    def __getattr__(self, name: str):
        if name == "and":
            return self.and_
        return super().__getattr__(name)

    def to_carrier(self):
        from foggy.dataset_model.impl.model import (
            AggregateRelationConditionDef,
            AggregateRelationDef,
            AggregateRelationFilterDef,
            AggregateRelationMeasureDef,
        )

        return AggregateRelationDef(
            join_type=self.join_type,
            left_model=self.left.model_name,
            right_model=self.right.model_name,
            alias=self.alias,
            group_by=[item["field"] for item in self._group_by],
            filters=[
                AggregateRelationFilterDef(
                    model=item["model"],
                    field=item["field"],
                    op=item["op"],
                    value=item.get("value"),
                )
                for item in self._filters
            ],
            measures=[
                AggregateRelationMeasureDef(
                    aggregation=item["aggregation"],
                    field=item.get("field"),
                    model=item.get("model"),
                    alias=item["alias"],
                    distinct=item.get("distinct", False),
                )
                for item in self._measures
            ],
            conditions=[
                AggregateRelationConditionDef(
                    left_model=condition.left_model_name,
                    left_field=condition.left_field_ref,
                    right_model=condition.right_model_name,
                    right_field=condition.right_field_ref,
                )
                for condition in self.conditions
            ],
        )


class TableModelProxy:
    """Dynamic proxy for table model field access in QM definitions.

    Aligned with Java TableModelProxy (PropertyHolder + PropertyFunction).

    Usage::

        fo = TableModelProxy("FactOrderModel")
        fo.orderId           -> ColumnRef("FactOrderModel", "orderId")
        fo.customer          -> DimensionProxy(["customer"])
        fo.customer$id       -> ColumnRef(..., "customer$id")
        fo.left_join(fp)     -> JoinBuilder(fo, fp, "LEFT")
    """

    def __init__(self, model_name: str, alias: Optional[str] = None):
        self._model_name = model_name
        self._alias = alias

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def effective_alias(self) -> str:
        return self._alias or self._model_name

    def __getattr__(self, name: str) -> ColumnRef | DimensionProxy:
        # Skip internal Python attributes
        if name.startswith("_"):
            raise AttributeError(name)

        # Handle dimension property: customer$memberLevel
        if "$" in name:
            return ColumnRef(self._model_name, name)

        return DimensionProxy(self, [name])

    def left_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "LEFT")

    def inner_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "INNER")

    def right_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "RIGHT")

    def leftJoin(self, other: TableModelProxy) -> JoinBuilder:
        return self.left_join(other)

    def leftJoinAggregate(self, other: TableModelProxy) -> UnsupportedAggregateJoinBuilder:
        return UnsupportedAggregateJoinBuilder(self, other)

    def filterEq(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return UnsupportedAggregateRelationProxy(self._model_name).filterEq(*args, **kwargs)

    def groupBy(self, *args, **kwargs) -> UnsupportedAggregateRelationProxy:
        return UnsupportedAggregateRelationProxy(self._model_name).groupBy(*args, **kwargs)

    def innerJoin(self, other: TableModelProxy) -> JoinBuilder:
        return self.inner_join(other)

    def rightJoin(self, other: TableModelProxy) -> JoinBuilder:
        return self.right_join(other)

    def __repr__(self) -> str:
        if self._alias:
            return f"TableModelProxy({self._model_name!r}, alias={self._alias!r})"
        return f"TableModelProxy({self._model_name!r})"
