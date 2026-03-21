"""TableModelProxy — dynamic field access for QM definitions.

Aligned with Java TableModelProxy + DimensionProxy + ColumnRef.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


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

    def on(self, left_ref: ColumnRef | str, right_ref: ColumnRef | str) -> JoinBuilder:
        """Set JOIN condition.

        Args can be ColumnRef or string field names.
        """
        self.on_left_key = (
            left_ref.field_ref if isinstance(left_ref, ColumnRef) else left_ref
        )
        self.on_right_key = (
            right_ref.field_ref if isinstance(right_ref, ColumnRef) else right_ref
        )
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

        # Return DimensionProxy for chained access
        return DimensionProxy(self, [name])

    def left_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "LEFT")

    def inner_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "INNER")

    def right_join(self, other: TableModelProxy) -> JoinBuilder:
        return JoinBuilder(self, other, "RIGHT")

    def __repr__(self) -> str:
        if self._alias:
            return f"TableModelProxy({self._model_name!r}, alias={self._alias!r})"
        return f"TableModelProxy({self._model_name!r})"
