"""Built-in Json global for FSScript.

Provides JSON parsing and stringification functions.
"""

from typing import Any, Dict, List, Optional, Union
import json


class JsonGlobal:
    """Built-in JSON utilities for FSScript.

    Provides functions for parsing and stringifying JSON data.
    """

    @staticmethod
    def parse(text: str) -> Any:
        """Parse a JSON string.

        Args:
            text: JSON string

        Returns:
            Parsed value (dict, list, or primitive)
        """
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def stringify(value: Any, replacer: Any = None, space: Any = None) -> str:
        """Convert a value to JSON string.

        Args:
            value: Value to convert
            replacer: Replacer function or array (currently ignored)
            space: Indentation level (number) or string for pretty print

        Returns:
            JSON string
        """
        if value is None:
            return "null"

        # Handle space parameter for indentation
        indent = None
        if space is not None:
            if isinstance(space, int):
                indent = max(0, min(space, 10))  # Cap at 10
            elif isinstance(space, str):
                indent = space[:10]  # Cap at 10 chars

        try:
            return json.dumps(value, ensure_ascii=False, indent=indent)
        except (TypeError, ValueError):
            # Try to handle non-serializable values
            return JsonGlobal._stringify_fallback(value, indent)

    @staticmethod
    def _stringify_fallback(value: Any, indent: Optional[int] = None) -> str:
        """Fallback stringify for non-serializable values.

        Args:
            value: Value to convert
            indent: Indentation level

        Returns:
            JSON string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return json.dumps(value)
        elif isinstance(value, list):
            items = [JsonGlobal._stringify_fallback(item) for item in value]
            if indent:
                return "[\n" + ",\n".join("  " + item for item in items) + "\n]"
            return "[" + ", ".join(items) + "]"
        elif isinstance(value, dict):
            pairs = []
            for k, v in value.items():
                key = json.dumps(str(k))
                val = JsonGlobal._stringify_fallback(v)
                pairs.append(f"{key}: {val}")
            if indent:
                return "{\n" + ",\n".join("  " + p for p in pairs) + "\n}"
            return "{" + ", ".join(pairs) + "}"
        else:
            # Convert to string
            return json.dumps(str(value))

    @staticmethod
    def valid(text: str) -> bool:
        """Check if a string is valid JSON.

        Args:
            text: String to check

        Returns:
            True if valid JSON
        """
        if text is None:
            return False
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    @staticmethod
    def get(value: Any, path: str, default: Any = None) -> Any:
        """Get a value from a nested structure using path.

        Args:
            value: JSON value
            path: Dot-separated path (e.g., "user.address.city")
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        if value is None or path is None:
            return default

        parts = path.split(".")
        current = value

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return default
                except ValueError:
                    return default
            else:
                return default

            if current is None:
                return default

        return current

    @staticmethod
    def set(value: Any, path: str, new_value: Any) -> Any:
        """Set a value in a nested structure using path.

        Args:
            value: JSON value (will be modified if dict/list)
            path: Dot-separated path
            new_value: Value to set

        Returns:
            Modified value
        """
        if path is None:
            return value

        parts = path.split(".")
        current = value

        for i, part in enumerate(parts[:-1]):
            if isinstance(current, dict):
                if part not in current:
                    # Auto-create nested structure
                    current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return value
                except ValueError:
                    return value
            else:
                return value

        # Set the final value
        if isinstance(current, dict):
            current[parts[-1]] = new_value
        elif isinstance(current, list):
            try:
                index = int(parts[-1])
                if 0 <= index < len(current):
                    current[index] = new_value
            except ValueError:
                pass

        return value

    @staticmethod
    def merge(base: Any, override: Any) -> Any:
        """Deep merge two JSON values.

        Args:
            base: Base value
            override: Override value

        Returns:
            Merged value
        """
        if base is None:
            return JsonGlobal._deep_copy(override)
        if override is None:
            return JsonGlobal._deep_copy(base)

        if isinstance(base, dict) and isinstance(override, dict):
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = JsonGlobal.merge(result[key], value)
                else:
                    result[key] = JsonGlobal._deep_copy(value)
            return result
        elif isinstance(base, list) and isinstance(override, list):
            # For lists, override wins
            return JsonGlobal._deep_copy(override)
        else:
            return JsonGlobal._deep_copy(override)

    @staticmethod
    def _deep_copy(value: Any) -> Any:
        """Deep copy a value.

        Args:
            value: Value to copy

        Returns:
            Deep copy
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        elif isinstance(value, list):
            return [JsonGlobal._deep_copy(item) for item in value]
        elif isinstance(value, dict):
            return {k: JsonGlobal._deep_copy(v) for k, v in value.items()}
        else:
            return value

    @staticmethod
    def keys(value: Any) -> List[str]:
        """Get keys of an object.

        Args:
            value: Object value

        Returns:
            List of keys
        """
        if isinstance(value, dict):
            return list(value.keys())
        return []

    @staticmethod
    def values(value: Any) -> List[Any]:
        """Get values of an object.

        Args:
            value: Object value

        Returns:
            List of values
        """
        if isinstance(value, dict):
            return list(value.values())
        return []

    @staticmethod
    def entries(value: Any) -> List[List[Any]]:
        """Get entries of an object.

        Args:
            value: Object value

        Returns:
            List of [key, value] pairs
        """
        if isinstance(value, dict):
            return [[k, v] for k, v in value.items()]
        return []

    @staticmethod
    def from_entries(entries: List[List[Any]]) -> Dict[str, Any]:
        """Create object from entries.

        Args:
            entries: List of [key, value] pairs

        Returns:
            Object
        """
        result = {}
        for entry in entries:
            if isinstance(entry, list) and len(entry) >= 2:
                result[str(entry[0])] = entry[1]
        return result

    @staticmethod
    def clone(value: Any) -> Any:
        """Deep clone a JSON value.

        Args:
            value: Value to clone

        Returns:
            Cloned value
        """
        return JsonGlobal._deep_copy(value)

    @staticmethod
    def equals(a: Any, b: Any) -> bool:
        """Deep compare two JSON values.

        Args:
            a: First value
            b: Second value

        Returns:
            True if equal
        """
        if type(a) != type(b):
            return False
        if isinstance(a, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(JsonGlobal.equals(a[k], b[k]) for k in a)
        elif isinstance(a, list):
            if len(a) != len(b):
                return False
            return all(JsonGlobal.equals(x, y) for x, y in zip(a, b))
        else:
            return a == b

    @staticmethod
    def type_of(value: Any) -> str:
        """Get the JSON type of a value.

        Args:
            value: Value to check

        Returns:
            Type name (object, array, string, number, boolean, null)
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"

    def get_functions(self) -> Dict[str, Any]:
        """Get all JSON functions as dictionary.

        Returns:
            Dictionary of function name to function
        """
        return {
            "parse": self.parse,
            "stringify": self.stringify,
            "valid": self.valid,
            "get": self.get,
            "set": self.set,
            "merge": self.merge,
            "keys": self.keys,
            "values": self.values,
            "entries": self.entries,
            "fromEntries": self.from_entries,
            "clone": self.clone,
            "equals": self.equals,
            "typeOf": self.type_of,
        }


__all__ = ["JsonGlobal"]