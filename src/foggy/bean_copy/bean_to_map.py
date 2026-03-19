"""Bean to Map conversion utilities."""

from dataclasses import asdict, fields, is_dataclass
from typing import Any, Dict, Optional, Type, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T")


class Bean2MapUtils:
    """Convert objects to dictionaries.

    Supports:
    - Pydantic BaseModel
    - dataclass
    - Regular objects with __dict__
    """

    @staticmethod
    def to_dict(
        obj: Any,
        exclude_none: bool = False,
        exclude_empty: bool = False,
        by_alias: bool = False,
    ) -> Dict[str, Any]:
        """Convert object to dictionary.

        Args:
            obj: Object to convert
            exclude_none: Exclude None values
            exclude_empty: Exclude empty strings/lists/dicts
            by_alias: Use field aliases (Pydantic only)

        Returns:
            Dictionary representation
        """
        if obj is None:
            return {}

        # Pydantic BaseModel
        if isinstance(obj, BaseModel):
            result = obj.model_dump(
                by_alias=by_alias,
                exclude_none=exclude_none,
            )
            if exclude_empty:
                result = {k: v for k, v in result.items() if not Bean2MapUtils._is_empty(v)}
            return result

        # dataclass
        if is_dataclass(obj) and not isinstance(obj, type):
            result = asdict(obj)
            if exclude_none:
                result = {k: v for k, v in result.items() if v is not None}
            if exclude_empty:
                result = {k: v for k, v in result.items() if not Bean2MapUtils._is_empty(v)}
            return result

        # Regular object with __dict__
        if hasattr(obj, "__dict__"):
            result = dict(obj.__dict__)
            if exclude_none:
                result = {k: v for k, v in result.items() if v is not None}
            if exclude_empty:
                result = {k: v for k, v in result.items() if not Bean2MapUtils._is_empty(v)}
            return result

        # Already a dict
        if isinstance(obj, dict):
            result = dict(obj)
            if exclude_none:
                result = {k: v for k, v in result.items() if v is not None}
            if exclude_empty:
                result = {k: v for k, v in result.items() if not Bean2MapUtils._is_empty(v)}
            return result

        raise TypeError(f"Cannot convert {type(obj)} to dict")

    @staticmethod
    def _is_empty(value: Any) -> bool:
        """Check if value is empty (not None but empty container or string)."""
        if value is None:
            return False  # None is handled by exclude_none
        if isinstance(value, str) and value == "":
            return True
        if isinstance(value, (list, tuple, set)) and len(value) == 0:
            return True
        if isinstance(value, dict) and len(value) == 0:
            return True
        return False

    @staticmethod
    def to_map(obj: Any, **kwargs) -> Dict[str, Any]:
        """Alias for to_dict."""
        return Bean2MapUtils.to_dict(obj, **kwargs)

    @staticmethod
    def to_json_str(
        obj: Any,
        exclude_none: bool = False,
        exclude_empty: bool = False,
        indent: bool = False,
    ) -> str:
        """Convert object to JSON string.

        Args:
            obj: Object to convert
            exclude_none: Exclude None values
            exclude_empty: Exclude empty values
            indent: Pretty print

        Returns:
            JSON string
        """
        import json

        data = Bean2MapUtils.to_dict(obj, exclude_none=exclude_none, exclude_empty=exclude_empty)
        if indent:
            return json.dumps(data, indent=2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def flat_map(
        obj: Any,
        prefix: str = "",
        separator: str = ".",
        exclude_none: bool = True,
    ) -> Dict[str, Any]:
        """Flatten nested object to single-level dictionary.

        Args:
            obj: Object to flatten
            prefix: Key prefix
            separator: Key separator
            exclude_none: Exclude None values

        Returns:
            Flattened dictionary
        """
        result: Dict[str, Any] = {}
        data = Bean2MapUtils.to_dict(obj)

        def _flatten(d: Dict[str, Any], pre: str = "") -> None:
            for key, value in d.items():
                new_key = f"{pre}{separator}{key}" if pre else key
                if isinstance(value, dict):
                    _flatten(value, new_key)
                elif isinstance(value, (list, tuple)):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            _flatten(item, f"{new_key}[{i}]")
                        else:
                            if not exclude_none or item is not None:
                                result[f"{new_key}[{i}]"] = item
                else:
                    if not exclude_none or value is not None:
                        result[new_key] = value

        _flatten(data, prefix)
        return result