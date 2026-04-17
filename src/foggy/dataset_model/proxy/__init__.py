"""TableModelProxy — dynamic field access for QM definitions.

Aligned with Java TableModelProxy + DimensionProxy + ColumnRef.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


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

    def innerJoin(self, other: TableModelProxy) -> JoinBuilder:
        return self.inner_join(other)

    def rightJoin(self, other: TableModelProxy) -> JoinBuilder:
        return self.right_join(other)

    def __repr__(self) -> str:
        if self._alias:
            return f"TableModelProxy({self._model_name!r}, alias={self._alias!r})"
        return f"TableModelProxy({self._model_name!r})"
