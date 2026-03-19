"""JSON utilities for Foggy Framework."""

import json
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import orjson

T = TypeVar("T")


class JsonUtils:
    """JSON utility functions using orjson for performance."""

    @staticmethod
    def to_json(
        obj: Any,
        indent: bool = False,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
    ) -> str:
        """Convert object to JSON string.

        Args:
            obj: Object to serialize
            indent: Whether to indent output
            ensure_ascii: Whether to escape non-ASCII characters
            sort_keys: Whether to sort dictionary keys

        Returns:
            JSON string
        """
        option = 0
        if indent:
            option |= orjson.OPT_INDENT_2
        if sort_keys:
            option |= orjson.OPT_SORT_KEYS

        result = orjson.dumps(obj, option=option)
        return result.decode("utf-8")

    @staticmethod
    def to_json_bytes(obj: Any, sort_keys: bool = False) -> bytes:
        """Convert object to JSON bytes.

        Args:
            obj: Object to serialize
            sort_keys: Whether to sort dictionary keys

        Returns:
            JSON bytes
        """
        option = orjson.OPT_SORT_KEYS if sort_keys else 0
        return orjson.dumps(obj, option=option)

    @staticmethod
    def from_json(s: Union[str, bytes]) -> Any:
        """Parse JSON string/bytes.

        Args:
            s: JSON string or bytes

        Returns:
            Parsed object
        """
        if isinstance(s, str):
            s = s.encode("utf-8")
        return orjson.loads(s)

    @staticmethod
    def from_json_typed(s: Union[str, bytes], cls: Type[T]) -> T:
        """Parse JSON string/bytes into typed object.

        Args:
            s: JSON string or bytes
            cls: Target class (must support from_dict or __init__)

        Returns:
            Typed object
        """
        data = JsonUtils.from_json(s)
        if hasattr(cls, "from_dict"):
            return cls.from_dict(data)  # type: ignore
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)  # type: ignore
        return cls(**data)

    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        """Convert object to dictionary.

        Args:
            obj: Object to convert

        Returns:
            Dictionary representation
        """
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore
        if hasattr(obj, "to_dict"):
            return obj.to_dict()  # type: ignore
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return dict(obj)

    @staticmethod
    def prettify(obj: Any) -> str:
        """Convert object to prettified JSON string.

        Args:
            obj: Object to serialize

        Returns:
            Prettified JSON string
        """
        return JsonUtils.to_json(obj, indent=True, sort_keys=True)

    @staticmethod
    def is_valid_json(s: str) -> bool:
        """Check if string is valid JSON.

        Args:
            s: String to check

        Returns:
            True if valid JSON
        """
        try:
            json.loads(s)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    @staticmethod
    def deep_copy(obj: Any) -> Any:
        """Deep copy object via JSON serialization.

        Args:
            obj: Object to copy

        Returns:
            Deep copy of object
        """
        return JsonUtils.from_json(JsonUtils.to_json(obj))

    @staticmethod
    def merge(*dicts: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple dictionaries.

        Later dictionaries override earlier ones.

        Args:
            *dicts: Dictionaries to merge

        Returns:
            Merged dictionary
        """
        result: Dict[str, Any] = {}
        for d in dicts:
            result.update(d)
        return result

    @staticmethod
    def get_path(data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get value at path in nested dictionary.

        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., "user.address.city")
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @staticmethod
    def set_path(data: Dict[str, Any], path: str, value: Any) -> None:
        """Set value at path in nested dictionary.

        Args:
            data: Dictionary to modify
            path: Dot-separated path (e.g., "user.address.city")
            value: Value to set
        """
        keys = path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value