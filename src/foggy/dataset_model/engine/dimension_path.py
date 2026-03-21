"""DimensionPath -- segment-based path for nested dimension traversal.

Handles snowflake schema dimension paths where dimensions can be nested
through multiple join levels.

Examples:
  "product"                -> DimensionPath(["product"])
  "product.category"       -> DimensionPath(["product", "category"])
  "product.category.group" -> DimensionPath(["product", "category", "group"])

Format conversions:
  dot format:        "product.category"
  underscore format: "product_category"
  column ref:        "product.category$id"
  column alias:      "product_category$id"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class DimensionPath:
    """Segment-based path for nested dimension traversal (snowflake schema).

    Aligned with Java DimensionPath.java. Each segment represents a
    dimension table hop in a snowflake join chain.
    """

    segments: List[str]
    """Path segments, e.g. ["product", "category"]."""

    column_name: Optional[str] = field(default=None)
    """Leaf column name, e.g. "id", "caption", "categoryId"."""

    # ------------------------------------------------------------------
    # Format conversions
    # ------------------------------------------------------------------

    def to_dot_format(self) -> str:
        """Return dot-separated path, e.g. "product.category"."""
        return ".".join(self.segments)

    def to_underscore_format(self) -> str:
        """Return underscore-separated path, e.g. "product_category"."""
        return "_".join(self.segments)

    def to_column_ref(self) -> str:
        """Return column reference using dot + $, e.g. "product.category$id".

        Raises ValueError if column_name is not set.
        """
        if self.column_name is None:
            raise ValueError("column_name is not set; call with_column() first")
        return f"{self.to_dot_format()}${self.column_name}"

    def to_column_alias(self) -> str:
        """Return column alias using underscore + $, e.g. "product_category$id".

        Raises ValueError if column_name is not set.
        """
        if self.column_name is None:
            raise ValueError("column_name is not set; call with_column() first")
        return f"{self.to_underscore_format()}${self.column_name}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def depth(self) -> int:
        """Number of segments in the path."""
        return len(self.segments)

    @property
    def is_nested(self) -> bool:
        """True when path has more than one segment (snowflake join)."""
        return self.depth > 1

    @property
    def root(self) -> str:
        """First segment (root dimension)."""
        return self.segments[0]

    @property
    def leaf(self) -> str:
        """Last segment (leaf dimension)."""
        return self.segments[-1]

    # ------------------------------------------------------------------
    # Derivation helpers
    # ------------------------------------------------------------------

    def parent(self) -> Optional[DimensionPath]:
        """Return path without the last segment, or None if depth == 1."""
        if self.depth <= 1:
            return None
        return DimensionPath(segments=self.segments[:-1])

    def append(self, segment: str) -> DimensionPath:
        """Return a new path with *segment* appended."""
        return DimensionPath(segments=[*self.segments, segment])

    def with_column(self, column_name: str) -> DimensionPath:
        """Return a copy with the given *column_name* set."""
        return DimensionPath(segments=self.segments, column_name=column_name)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse(dot_path: str) -> DimensionPath:
        """Parse a dot-format path, optionally with a ``$column`` suffix.

        Examples::

            "product"             -> segments=["product"], column_name=None
            "product.category"    -> segments=["product","category"], column_name=None
            "product.category$id" -> segments=["product","category"], column_name="id"
        """
        column_name: Optional[str] = None
        path_part = dot_path

        if "$" in dot_path:
            path_part, column_name = dot_path.rsplit("$", 1)

        segments = path_part.split(".")
        if not segments or any(s == "" for s in segments):
            raise ValueError(f"Invalid dimension path: {dot_path!r}")

        return DimensionPath(segments=segments, column_name=column_name)

    @staticmethod
    def parse_underscore(underscore_path: str) -> DimensionPath:
        """Parse an underscore-format path, optionally with a ``$column`` suffix.

        Examples::

            "product"                -> segments=["product"], column_name=None
            "product_category"       -> segments=["product","category"], column_name=None
            "product_category$caption" -> segments=["product","category"], column_name="caption"
        """
        column_name: Optional[str] = None
        path_part = underscore_path

        if "$" in underscore_path:
            path_part, column_name = underscore_path.rsplit("$", 1)

        segments = path_part.split("_")
        if not segments or any(s == "" for s in segments):
            raise ValueError(f"Invalid dimension path: {underscore_path!r}")

        return DimensionPath(segments=segments, column_name=column_name)

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        if self.column_name:
            return self.to_column_ref()
        return self.to_dot_format()

    def __repr__(self) -> str:
        parts = f"segments={self.segments!r}"
        if self.column_name:
            parts += f", column_name={self.column_name!r}"
        return f"DimensionPath({parts})"
