"""Conversion utilities for FSScript.

Provides utilities for converting between different data types
and for map-to-object and object-to-map conversions.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, get_type_hints
from dataclasses import fields, is_dataclass
from pydantic import BaseModel
import json

T = TypeVar("T")


class ConversionUtils:
    """Utility class for data type conversions."""

    @staticmethod
    def to_string(value: Any) -> str:
        """Convert any value to string representation.

        Args:
            value: Value to convert

        Returns:
            String representation
        """
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        else:
            return str(value)

    @staticmethod
    def to_number(value: Any, default: float = 0.0) -> float:
        """Convert any value to number.

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            Numeric value
        """
        if value is None:
            return default
        elif isinstance(value, bool):
            return 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            try:
                # Try integer first
                if "." not in value:
                    return float(int(value))
                return float(value)
            except ValueError:
                return default
        else:
            return default

    @staticmethod
    def to_integer(value: Any, default: int = 0) -> int:
        """Convert any value to integer.

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            Integer value
        """
        return int(ConversionUtils.to_number(value, float(default)))

    @staticmethod
    def to_boolean(value: Any) -> bool:
        """Convert any value to boolean.

        Args:
            value: Value to convert

        Returns:
            Boolean value
        """
        if value is None:
            return False
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value != 0
        elif isinstance(value, str):
            lower = value.lower().strip()
            return lower not in ("", "false", "0", "no", "n", "null", "none")
        elif isinstance(value, (list, dict)):
            return len(value) > 0
        else:
            return True

    @staticmethod
    def to_list(value: Any) -> List[Any]:
        """Convert any value to list.

        Args:
            value: Value to convert

        Returns:
            List value
        """
        if value is None:
            return []
        elif isinstance(value, list):
            return value
        elif isinstance(value, dict):
            return list(value.values())
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
                return [parsed]
            except json.JSONDecodeError:
                return [value]
        else:
            return [value]

    @staticmethod
    def to_dict(value: Any) -> Dict[str, Any]:
        """Convert any value to dictionary.

        Args:
            value: Value to convert

        Returns:
            Dictionary value
        """
        if value is None:
            return {}
        elif isinstance(value, dict):
            return value
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
                return {"value": parsed}
            except json.JSONDecodeError:
                return {"value": value}
        elif isinstance(value, list):
            return {str(i): v for i, v in enumerate(value)}
        else:
            return {"value": value}

    @staticmethod
    def object_to_map(obj: Any) -> Dict[str, Any]:
        """Convert an object to a dictionary/map.

        Handles Pydantic models, dataclasses, and regular objects.

        Args:
            obj: Object to convert

        Returns:
            Dictionary representation
        """
        if obj is None:
            return {}
        elif isinstance(obj, dict):
            return obj.copy()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        elif is_dataclass(obj):
            return {f.name: getattr(obj, f.name) for f in fields(obj)}
        elif hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        else:
            return {"value": obj}

    @staticmethod
    def map_to_object(data: Dict[str, Any], target_class: Type[T]) -> T:
        """Convert a dictionary to an object.

        Handles Pydantic models, dataclasses, and regular classes.

        Args:
            data: Dictionary to convert
            target_class: Target class type

        Returns:
            Instance of target class
        """
        if issubclass(target_class, BaseModel):
            return target_class(**data)
        elif is_dataclass(target_class):
            # Get field names
            field_names = {f.name for f in fields(target_class)}
            filtered_data = {k: v for k, v in data.items() if k in field_names}
            return target_class(**filtered_data)
        else:
            # Regular class - set attributes directly
            instance = target_class.__new__(target_class)
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            return instance

    @staticmethod
    def deep_clone(value: Any) -> Any:
        """Deep clone a value.

        Args:
            value: Value to clone

        Returns:
            Deep copy of value
        """
        if value is None:
            return None
        elif isinstance(value, (int, float, str, bool)):
            return value
        elif isinstance(value, list):
            return [ConversionUtils.deep_clone(item) for item in value]
        elif isinstance(value, dict):
            return {k: ConversionUtils.deep_clone(v) for k, v in value.items()}
        elif isinstance(value, BaseModel):
            return value.model_copy(deep=True)
        elif is_dataclass(value):
            data = ConversionUtils.object_to_map(value)
            return ConversionUtils.map_to_object(data, type(value))
        else:
            return value

    @staticmethod
    def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two dictionaries, with override taking precedence.

        Performs deep merge for nested dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConversionUtils.merge_dicts(result[key], value)
            else:
                result[key] = ConversionUtils.deep_clone(value)

        return result


class MapToObjectConverter:
    """Converter for map-to-object conversions with type coercion."""

    def __init__(self, strict: bool = False):
        """Initialize converter.

        Args:
            strict: If True, raise errors on conversion failures
        """
        self.strict = strict

    def convert(self, data: Dict[str, Any], target_class: Type[T]) -> T:
        """Convert data to target class with type coercion.

        Args:
            data: Source data
            target_class: Target class

        Returns:
            Converted instance
        """
        if issubclass(target_class, BaseModel):
            return target_class(**data)
        elif is_dataclass(target_class):
            return self._convert_to_dataclass(data, target_class)
        else:
            return ConversionUtils.map_to_object(data, target_class)

    def _convert_to_dataclass(self, data: Dict[str, Any], target_class: Type[T]) -> T:
        """Convert data to dataclass with type coercion.

        Args:
            data: Source data
            target_class: Target dataclass

        Returns:
            Dataclass instance
        """
        field_names = {f.name: f for f in fields(target_class)}
        kwargs = {}

        for name, field in field_names.items():
            if name in data:
                value = data[name]
                # TODO: Add type coercion based on field.type
                kwargs[name] = value

        return target_class(**kwargs)


class FsscriptConversionService:
    """Service for FSScript type conversions.

    Provides a registry of converters for different types.
    """

    def __init__(self):
        """Initialize conversion service."""
        self._converters: Dict[type, callable] = {}
        self._register_default_converters()

    def _register_default_converters(self) -> None:
        """Register default type converters."""
        self._converters[str] = ConversionUtils.to_string
        self._converters[int] = ConversionUtils.to_integer
        self._converters[float] = ConversionUtils.to_number
        self._converters[bool] = ConversionUtils.to_boolean
        self._converters[list] = ConversionUtils.to_list
        self._converters[dict] = ConversionUtils.to_dict

    def register_converter(self, target_type: type, converter: callable) -> None:
        """Register a custom type converter.

        Args:
            target_type: Target type
            converter: Converter function (Any -> target_type)
        """
        self._converters[target_type] = converter

    def convert(self, value: Any, target_type: type) -> Any:
        """Convert a value to the target type.

        Args:
            value: Value to convert
            target_type: Target type

        Returns:
            Converted value
        """
        if target_type in self._converters:
            return self._converters[target_type](value)
        return value

    def can_convert(self, target_type: type) -> bool:
        """Check if conversion to target type is supported.

        Args:
            target_type: Target type

        Returns:
            True if conversion is supported
        """
        return target_type in self._converters