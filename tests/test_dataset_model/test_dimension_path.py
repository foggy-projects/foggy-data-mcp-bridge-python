"""Unit tests for DimensionPath -- segment-based nested dimension path traversal."""

import pytest

from foggy.dataset_model.engine.dimension_path import DimensionPath


class TestDimensionPathBasic:
    """Basic construction and format conversion tests."""

    def test_single_segment(self):
        """Single segment dot format."""
        p = DimensionPath(segments=["product"])
        assert p.to_dot_format() == "product"

    def test_single_segment_underscore(self):
        """Single segment underscore format (same as dot for one segment)."""
        p = DimensionPath(segments=["product"])
        assert p.to_underscore_format() == "product"

    def test_nested_path(self):
        """Two-segment dot format."""
        p = DimensionPath(segments=["product", "category"])
        assert p.to_dot_format() == "product.category"

    def test_underscore_format(self):
        """Two-segment underscore format."""
        p = DimensionPath(segments=["product", "category"])
        assert p.to_underscore_format() == "product_category"

    def test_three_level_dot(self):
        """Three-segment dot format."""
        p = DimensionPath(segments=["product", "category", "group"])
        assert p.to_dot_format() == "product.category.group"

    def test_three_level_underscore(self):
        """Three-segment underscore format."""
        p = DimensionPath(segments=["product", "category", "group"])
        assert p.to_underscore_format() == "product_category_group"


class TestDimensionPathColumn:
    """Column reference and alias tests."""

    def test_column_ref(self):
        """Column ref uses dot + $."""
        p = DimensionPath(segments=["product", "category"], column_name="id")
        assert p.to_column_ref() == "product.category$id"

    def test_column_alias(self):
        """Column alias uses underscore + $."""
        p = DimensionPath(segments=["product", "category"], column_name="id")
        assert p.to_column_alias() == "product_category$id"

    def test_column_ref_single_segment(self):
        """Column ref for single segment."""
        p = DimensionPath(segments=["product"], column_name="name")
        assert p.to_column_ref() == "product$name"

    def test_column_alias_single_segment(self):
        """Column alias for single segment."""
        p = DimensionPath(segments=["product"], column_name="name")
        assert p.to_column_alias() == "product$name"

    def test_column_ref_no_column_raises(self):
        """to_column_ref raises when column_name is not set."""
        p = DimensionPath(segments=["product", "category"])
        with pytest.raises(ValueError):
            p.to_column_ref()

    def test_column_alias_no_column_raises(self):
        """to_column_alias raises when column_name is not set."""
        p = DimensionPath(segments=["product"])
        with pytest.raises(ValueError):
            p.to_column_alias()

    def test_with_column(self):
        """with_column returns a new path with column_name set."""
        p = DimensionPath(segments=["product", "category"])
        p2 = p.with_column("id")
        assert p2.to_column_ref() == "product.category$id"
        assert p2.to_column_alias() == "product_category$id"
        # Original unchanged
        assert p.column_name is None


class TestDimensionPathProperties:
    """Tests for depth, is_nested, root, leaf."""

    def test_depth_single(self):
        """Depth of single segment path."""
        p = DimensionPath(segments=["product"])
        assert p.depth == 1

    def test_depth_nested(self):
        """Depth of two-segment path."""
        p = DimensionPath(segments=["product", "category"])
        assert p.depth == 2

    def test_three_level_depth(self):
        """Depth of three-segment path."""
        p = DimensionPath(segments=["product", "category", "group"])
        assert p.depth == 3

    def test_is_nested_false(self):
        """Single segment is not nested."""
        p = DimensionPath(segments=["product"])
        assert p.is_nested is False

    def test_is_nested_true(self):
        """Two segments is nested."""
        p = DimensionPath(segments=["product", "category"])
        assert p.is_nested is True

    def test_root(self):
        """Root is the first segment."""
        p = DimensionPath(segments=["product", "category"])
        assert p.root == "product"

    def test_leaf(self):
        """Leaf is the last segment."""
        p = DimensionPath(segments=["product", "category"])
        assert p.leaf == "category"

    def test_root_single(self):
        """Root of single segment."""
        p = DimensionPath(segments=["product"])
        assert p.root == "product"

    def test_leaf_single(self):
        """Leaf of single segment is same as root."""
        p = DimensionPath(segments=["product"])
        assert p.leaf == "product"


class TestDimensionPathDerivation:
    """Tests for parent and append."""

    def test_parent(self):
        """Parent removes last segment."""
        p = DimensionPath(segments=["product", "category"])
        parent = p.parent()
        assert parent is not None
        assert parent.to_dot_format() == "product"

    def test_parent_of_root(self):
        """Parent of single segment is None."""
        p = DimensionPath(segments=["product"])
        assert p.parent() is None

    def test_parent_three_level(self):
        """Parent of three-level path."""
        p = DimensionPath(segments=["product", "category", "group"])
        parent = p.parent()
        assert parent is not None
        assert parent.to_dot_format() == "product.category"

    def test_append(self):
        """Append adds a segment."""
        p = DimensionPath(segments=["product", "category"])
        p2 = p.append("group")
        assert p2.to_dot_format() == "product.category.group"
        # Original unchanged
        assert p.depth == 2

    def test_append_to_single(self):
        """Append to single segment."""
        p = DimensionPath(segments=["product"])
        p2 = p.append("category")
        assert p2.to_dot_format() == "product.category"
        assert p2.depth == 2


class TestDimensionPathParsing:
    """Tests for parse and parse_underscore."""

    def test_parse_dot_single(self):
        """Parse single segment."""
        p = DimensionPath.parse("product")
        assert p.segments == ["product"]
        assert p.column_name is None

    def test_parse_dot_nested(self):
        """Parse two-segment dot path."""
        p = DimensionPath.parse("product.category")
        assert p.segments == ["product", "category"]
        assert p.column_name is None

    def test_parse_dot_with_column(self):
        """Parse dot path with $column."""
        p = DimensionPath.parse("product.category$id")
        assert p.segments == ["product", "category"]
        assert p.column_name == "id"

    def test_parse_single_with_column(self):
        """Parse single segment with $column."""
        p = DimensionPath.parse("product$name")
        assert p.segments == ["product"]
        assert p.column_name == "name"

    def test_parse_no_column(self):
        """Parse without $ yields None column_name."""
        p = DimensionPath.parse("product.category")
        assert p.column_name is None

    def test_parse_underscore_single(self):
        """Parse underscore single segment."""
        p = DimensionPath.parse_underscore("product")
        assert p.segments == ["product"]

    def test_parse_underscore_nested(self):
        """Parse underscore two-segment path."""
        p = DimensionPath.parse_underscore("product_category")
        assert p.segments == ["product", "category"]

    def test_parse_underscore_with_column(self):
        """Parse underscore path with $column."""
        p = DimensionPath.parse_underscore("product_category$caption")
        assert p.segments == ["product", "category"]
        assert p.column_name == "caption"

    def test_parse_three_level(self):
        """Parse three-level dot path."""
        p = DimensionPath.parse("product.category.group")
        assert p.segments == ["product", "category", "group"]
        assert p.depth == 3

    def test_parse_invalid_empty(self):
        """Parse empty string raises ValueError."""
        with pytest.raises(ValueError):
            DimensionPath.parse("")

    def test_parse_invalid_trailing_dot(self):
        """Parse trailing dot raises ValueError."""
        with pytest.raises(ValueError):
            DimensionPath.parse("product.")


class TestDimensionPathStr:
    """Tests for __str__ and __repr__."""

    def test_str_no_column(self):
        """str() without column shows dot format."""
        p = DimensionPath(segments=["product", "category"])
        assert str(p) == "product.category"

    def test_str_with_column(self):
        """str() with column shows column ref."""
        p = DimensionPath(segments=["product", "category"], column_name="id")
        assert str(p) == "product.category$id"

    def test_repr(self):
        """repr() includes class name and segments."""
        p = DimensionPath(segments=["product"])
        r = repr(p)
        assert "DimensionPath" in r
        assert "product" in r
