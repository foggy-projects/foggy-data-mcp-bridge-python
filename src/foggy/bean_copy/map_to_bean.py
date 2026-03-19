"""Map to Bean conversion utilities."""

from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, TypeVar, get_type_hints

from pydantic import BaseModel, ValidationError

T = TypeVar("T")


class Map2BeanUtils:
    """Convert dictionaries to objects.

    Supports:
    - Pydantic BaseModel
    - dataclass
    - Regular classes with __init__
    """

    @staticmethod
    def to_bean(
        data: Dict[str, Any],
        cls: Type[T],
        strict: bool = False,
        by_alias: bool = False,
    ) -> T:
        """Convert dictionary to object.

        Args:
            data: Dictionary to convert
            cls: Target class
            strict: Raise error on unknown fields (Pydantic only)
            by_alias: Use field aliases (Pydantic only)

        Returns:
            Instance of target class

        Raises:
            ValidationError: If Pydantic validation fails
            TypeError: If class type is not supported
        """
        if data is None:
            data = {}

        # Pydantic BaseModel
        if issubclass(cls, BaseModel):
            extra = "forbid" if strict else "ignore"
            # Create a copy of the model config to avoid modifying the original
            return cls.model_validate(data, context={"by_alias": by_alias})

        # dataclass
        if is_dataclass(cls) and not isinstance(cls, type):
            return Map2BeanUtils._to_dataclass(data, cls, strict)

        # Regular class with __init__
        return Map2BeanUtils._to_regular_class(data, cls)

    @staticmethod
    def _to_dataclass(data: Dict[str, Any], cls: Type[T], strict: bool) -> T:
        """Convert dict to dataclass."""
        type_hints = get_type_hints(cls)
        field_names = {f.name for f in fields(cls)}

        # Filter unknown fields if strict
        if strict:
            unknown = set(data.keys()) - field_names
            if unknown:
                raise ValueError(f"Unknown fields: {unknown}")

        # Get matching fields
        kwargs: Dict[str, Any] = {}
        for field_name in field_names:
            if field_name in data:
                value = data[field_name]
                # TODO: Handle nested dataclasses
                kwargs[field_name] = value

        return cls(**kwargs)

    @staticmethod
    def _to_regular_class(data: Dict[str, Any], cls: Type[T]) -> T:
        """Convert dict to regular class instance."""
        # Create instance without calling __init__
        instance = object.__new__(cls)

        # Set attributes
        for key, value in data.items():
            setattr(instance, key, value)

        return instance

    @staticmethod
    def from_json_str(
        json_str: str,
        cls: Type[T],
        strict: bool = False,
    ) -> T:
        """Convert JSON string to object.

        Args:
            json_str: JSON string
            cls: Target class
            strict: Raise error on unknown fields

        Returns:
            Instance of target class
        """
        import json

        data = json.loads(json_str)
        if isinstance(data, dict):
            return Map2BeanUtils.to_bean(data, cls, strict)
        if isinstance(data, list):
            # Handle list of objects
            raise TypeError("Expected JSON object, got array. Use from_json_list instead.")
        raise TypeError(f"Expected JSON object, got {type(data).__name__}")

    @staticmethod
    def from_json_list(
        json_str: str,
        cls: Type[T],
        strict: bool = False,
    ) -> list[T]:
        """Convert JSON array to list of objects.

        Args:
            json_str: JSON string
            cls: Target class
            strict: Raise error on unknown fields

        Returns:
            List of instances
        """
        import json

        data = json.loads(json_str)
        if not isinstance(data, list):
            raise TypeError(f"Expected JSON array, got {type(data).__name__}")

        return [Map2BeanUtils.to_bean(item, cls, strict) for item in data]

    @staticmethod
    def unflat_map(
        data: Dict[str, Any],
        separator: str = ".",
    ) -> Dict[str, Any]:
        """Unflatten dot-notation keys to nested dictionary.

        Args:
            data: Flattened dictionary
            separator: Key separator

        Returns:
            Nested dictionary
        """
        result: Dict[str, Any] = {}

        for key, value in data.items():
            parts = key.split(separator)
            current = result

            for i, part in enumerate(parts[:-1]):
                # Handle array index notation
                if part.endswith("]"):
                    array_key = part[: part.rfind("[")]
                    index = int(part[part.rfind("[") + 1 : -1])

                    if array_key not in current:
                        current[array_key] = []
                    while len(current[array_key]) <= index:
                        current[array_key].append({})

                    current = current[array_key][index]
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

            final_key = parts[-1]
            # Handle final array index
            if final_key.endswith("]"):
                array_key = final_key[: final_key.rfind("[")]
                index = int(final_key[final_key.rfind("[") + 1 : -1])

                if array_key not in current:
                    current[array_key] = []
                while len(current[array_key]) <= index:
                    current[array_key].append(None)
                current[array_key][index] = value
            else:
                current[final_key] = value

        return result

    @staticmethod
    def copy_properties(
        source: Any,
        target: Type[T],
        exclude: Optional[set[str]] = None,
        include: Optional[set[str]] = None,
    ) -> T:
        """Copy properties from source to new target instance.

        Args:
            source: Source object or dict
            target: Target class
            exclude: Fields to exclude
            include: Fields to include (only these)

        Returns:
            New instance of target class
        """
        if isinstance(source, dict):
            data = dict(source)
        else:
            data = Bean2MapUtils.to_dict(source)

        # Apply filters
        if exclude:
            data = {k: v for k, v in data.items() if k not in exclude}
        if include:
            data = {k: v for k, v in data.items() if k in include}

        return Map2BeanUtils.to_bean(data, target)


# Import here to avoid circular import
from foggy.bean_copy.bean_to_map import Bean2MapUtils