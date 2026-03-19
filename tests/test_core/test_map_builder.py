"""Unit tests for MapBuilder utility."""

import pytest
from foggy.core.common import MapBuilder


class TestMapBuilder:
    """Tests for MapBuilder fluent dictionary builder."""

    def test_empty_builder(self):
        """Test empty builder produces empty dict."""
        result = MapBuilder().build()
        assert result == {}

    def test_put_single(self):
        """Test putting single key-value pair."""
        result = MapBuilder().put("name", "John").build()
        assert result == {"name": "John"}

    def test_put_multiple(self):
        """Test putting multiple key-value pairs."""
        result = (
            MapBuilder()
            .put("name", "John")
            .put("age", 30)
            .put("active", True)
            .build()
        )
        assert result == {"name": "John", "age": 30, "active": True}

    def test_put_object(self):
        """Test put_object (alias for put)."""
        result = MapBuilder().put_object("key", "value").build()
        assert result == {"key": "value"}

    def test_put_if_not_none(self):
        """Test put_if_not_none only adds non-None values."""
        result = (
            MapBuilder()
            .put_if_not_none("exists", "value")
            .put_if_not_none("missing", None)
            .build()
        )
        assert result == {"exists": "value"}
        assert "missing" not in result

    def test_put_all(self):
        """Test adding all from another dict."""
        result = (
            MapBuilder()
            .put("a", 1)
            .put_all({"b": 2, "c": 3})
            .build()
        )
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_remove(self):
        """Test removing a key."""
        result = (
            MapBuilder()
            .put("a", 1)
            .put("b", 2)
            .remove("a")
            .build()
        )
        assert result == {"b": 2}

    def test_remove_nonexistent(self):
        """Test removing non-existent key does nothing."""
        result = (
            MapBuilder()
            .put("a", 1)
            .remove("nonexistent")
            .build()
        )
        assert result == {"a": 1}

    def test_clear_all(self):
        """Test clearing all entries."""
        result = (
            MapBuilder()
            .put("a", 1)
            .put("b", 2)
            .clear_all()
            .build()
        )
        assert result == {}

    def test_initial_values(self):
        """Test initializing with values."""
        result = MapBuilder({"initial": "value"}).put("added", "new").build()
        assert result == {"initial": "value", "added": "new"}

    def test_to_map_alias(self):
        """Test to_map is alias for build."""
        builder = MapBuilder().put("key", "value")
        assert builder.to_map() == builder.build()

    def test_create_factory(self):
        """Test create factory method."""
        result = MapBuilder.create().put("test", 1).build()
        assert result == {"test": 1}

    def test_from_dict_factory(self):
        """Test from_dict factory method."""
        result = MapBuilder.from_dict({"a": 1}).put("b", 2).build()
        assert result == {"a": 1, "b": 2}

    def test_chain_operations(self):
        """Test complex chain of operations."""
        result = (
            MapBuilder()
            .put("a", 1)
            .put("b", 2)
            .put("c", 3)
            .remove("b")
            .put("d", 4)
            .put_if_not_none("e", None)
            .put_all({"f": 5, "g": 6})
            .build()
        )
        assert result == {"a": 1, "c": 3, "d": 4, "f": 5, "g": 6}

    def test_nested_dict(self):
        """Test building nested dictionary."""
        result = (
            MapBuilder()
            .put("user", MapBuilder()
                 .put("name", "John")
                 .put("email", "john@example.com")
                 .build())
            .build()
        )
        assert result == {
            "user": {
                "name": "John",
                "email": "john@example.com",
            }
        }

    def test_list_value(self):
        """Test building dict with list value."""
        result = (
            MapBuilder()
            .put("items", [1, 2, 3])
            .build()
        )
        assert result == {"items": [1, 2, 3]}