"""Built-in Array global for FSScript.

Provides array manipulation functions available globally in FSScript.
"""

from typing import Any, Callable, Dict, List, Optional, Union


class ArrayGlobal:
    """Built-in array utilities for FSScript.

    Provides functions for creating, manipulating, and querying arrays.
    """

    @staticmethod
    def create(*args: Any) -> List[Any]:
        """Create an array from arguments.

        Args:
            *args: Elements

        Returns:
            New array
        """
        return list(args)

    @staticmethod
    def from_value(value: Any) -> List[Any]:
        """Create an array from a value.

        Args:
            value: Value (string, iterable, or single value)

        Returns:
            New array
        """
        if isinstance(value, list):
            return value.copy()
        elif isinstance(value, (tuple, set)):
            return list(value)
        elif isinstance(value, str):
            return list(value)
        elif isinstance(value, dict):
            return list(value.values())
        elif hasattr(value, "__iter__"):
            return list(value)
        else:
            return [value]

    @staticmethod
    def range(start: int, end: Optional[int] = None, step: int = 1) -> List[int]:
        """Create a range of integers.

        Args:
            start: Start value (or end if end is None)
            end: End value (exclusive)
            step: Step value

        Returns:
            List of integers
        """
        if end is None:
            return list(range(start))
        return list(range(start, end, step))

    @staticmethod
    def length(arr: List[Any]) -> int:
        """Get array length.

        Args:
            arr: Array

        Returns:
            Length
        """
        return len(arr) if arr else 0

    @staticmethod
    def push(arr: List[Any], *values: Any) -> int:
        """Push values to end of array.

        Args:
            arr: Array
            *values: Values to add

        Returns:
            New length
        """
        if arr is None:
            return 0
        arr.extend(values)
        return len(arr)

    @staticmethod
    def pop(arr: List[Any]) -> Any:
        """Pop last element from array.

        Args:
            arr: Array

        Returns:
            Removed element or None
        """
        if arr and len(arr) > 0:
            return arr.pop()
        return None

    @staticmethod
    def shift(arr: List[Any]) -> Any:
        """Remove first element from array.

        Args:
            arr: Array

        Returns:
            Removed element or None
        """
        if arr and len(arr) > 0:
            return arr.pop(0)
        return None

    @staticmethod
    def unshift(arr: List[Any], *values: Any) -> int:
        """Add values to beginning of array.

        Args:
            arr: Array
            *values: Values to add

        Returns:
            New length
        """
        if arr is None:
            return 0
        for i, v in enumerate(values):
            arr.insert(i, v)
        return len(arr)

    @staticmethod
    def slice(arr: List[Any], start: int = 0, end: Optional[int] = None) -> List[Any]:
        """Slice array.

        Args:
            arr: Array
            start: Start index
            end: End index (exclusive)

        Returns:
            Sliced array
        """
        if arr is None:
            return []
        return arr[start:end]

    @staticmethod
    def concat(*arrays: List[Any]) -> List[Any]:
        """Concatenate arrays.

        Args:
            *arrays: Arrays to concatenate

        Returns:
            Concatenated array
        """
        result = []
        for arr in arrays:
            if arr:
                result.extend(arr)
        return result

    @staticmethod
    def join(arr: List[Any], separator: str = ",") -> str:
        """Join array elements into string.

        Args:
            arr: Array
            separator: Separator string

        Returns:
            Joined string
        """
        if arr is None:
            return ""
        return separator.join(str(x) for x in arr)

    @staticmethod
    def reverse(arr: List[Any]) -> List[Any]:
        """Reverse array in place.

        Args:
            arr: Array

        Returns:
            Reversed array
        """
        if arr:
            arr.reverse()
        return arr or []

    @staticmethod
    def sort(arr: List[Any], key: Optional[Callable] = None) -> List[Any]:
        """Sort array.

        Args:
            arr: Array
            key: Optional key function

        Returns:
            Sorted array
        """
        if arr:
            arr.sort(key=key)
        return arr or []

    @staticmethod
    def index_of(arr: List[Any], value: Any) -> int:
        """Find index of value.

        Args:
            arr: Array
            value: Value to find

        Returns:
            Index or -1
        """
        if arr is None:
            return -1
        try:
            return arr.index(value)
        except ValueError:
            return -1

    @staticmethod
    def last_index_of(arr: List[Any], value: Any) -> int:
        """Find last index of value.

        Args:
            arr: Array
            value: Value to find

        Returns:
            Index or -1
        """
        if arr is None:
            return -1
        for i in range(len(arr) - 1, -1, -1):
            if arr[i] == value:
                return i
        return -1

    @staticmethod
    def contains(arr: List[Any], value: Any) -> bool:
        """Check if array contains value.

        Args:
            arr: Array
            value: Value to find

        Returns:
            True if contains
        """
        if arr is None:
            return False
        return value in arr

    @staticmethod
    def map(arr: List[Any], func: Callable) -> List[Any]:
        """Map array elements through function.

        Args:
            arr: Array
            func: Mapping function

        Returns:
            Mapped array
        """
        if arr is None or func is None:
            return []
        return [func(x) for x in arr]

    @staticmethod
    def filter(arr: List[Any], func: Callable) -> List[Any]:
        """Filter array elements.

        Args:
            arr: Array
            func: Filter function (returns bool)

        Returns:
            Filtered array
        """
        if arr is None or func is None:
            return []
        return [x for x in arr if func(x)]

    @staticmethod
    def reduce(arr: List[Any], func: Callable, initial: Any = None) -> Any:
        """Reduce array to single value.

        Args:
            arr: Array
            func: Reducer function (accumulator, value) -> new accumulator
            initial: Initial value

        Returns:
            Reduced value
        """
        if arr is None or len(arr) == 0:
            return initial
        if initial is not None:
            result = initial
            for x in arr:
                result = func(result, x)
        else:
            result = arr[0]
            for x in arr[1:]:
                result = func(result, x)
        return result

    @staticmethod
    def find(arr: List[Any], func: Callable) -> Any:
        """Find first element matching predicate.

        Args:
            arr: Array
            func: Predicate function

        Returns:
            Found element or None
        """
        if arr is None or func is None:
            return None
        for x in arr:
            if func(x):
                return x
        return None

    @staticmethod
    def find_index(arr: List[Any], func: Callable) -> int:
        """Find index of first element matching predicate.

        Args:
            arr: Array
            func: Predicate function

        Returns:
            Index or -1
        """
        if arr is None or func is None:
            return -1
        for i, x in enumerate(arr):
            if func(x):
                return i
        return -1

    @staticmethod
    def every(arr: List[Any], func: Callable) -> bool:
        """Check if all elements match predicate.

        Args:
            arr: Array
            func: Predicate function

        Returns:
            True if all match
        """
        if arr is None or len(arr) == 0:
            return True
        return all(func(x) for x in arr)

    @staticmethod
    def some(arr: List[Any], func: Callable) -> bool:
        """Check if any element matches predicate.

        Args:
            arr: Array
            func: Predicate function

        Returns:
            True if any matches
        """
        if arr is None or len(arr) == 0:
            return False
        return any(func(x) for x in arr)

    @staticmethod
    def flat(arr: List[Any], depth: int = 1) -> List[Any]:
        """Flatten nested arrays.

        Args:
            arr: Array
            depth: Flatten depth

        Returns:
            Flattened array
        """
        if arr is None:
            return []

        def flatten(items: List[Any], d: int) -> List[Any]:
            result = []
            for item in items:
                if isinstance(item, list) and d > 0:
                    result.extend(flatten(item, d - 1))
                else:
                    result.append(item)
            return result

        return flatten(arr, depth)

    @staticmethod
    def flat_map(arr: List[Any], func: Callable) -> List[Any]:
        """Map and flatten.

        Args:
            arr: Array
            func: Mapping function

        Returns:
            Flattened mapped array
        """
        if arr is None or func is None:
            return []
        result = []
        for x in arr:
            mapped = func(x)
            if isinstance(mapped, list):
                result.extend(mapped)
            else:
                result.append(mapped)
        return result

    @staticmethod
    def fill(arr: List[Any], value: Any, start: int = 0, end: Optional[int] = None) -> List[Any]:
        """Fill array with value.

        Args:
            arr: Array
            value: Fill value
            start: Start index
            end: End index (exclusive)

        Returns:
            Filled array
        """
        if arr is None:
            return []
        end = end or len(arr)
        for i in range(start, min(end, len(arr))):
            arr[i] = value
        return arr

    @staticmethod
    def copy(arr: List[Any]) -> List[Any]:
        """Create shallow copy of array.

        Args:
            arr: Array

        Returns:
            Copy of array
        """
        if arr is None:
            return []
        return arr.copy()

    @staticmethod
    def unique(arr: List[Any]) -> List[Any]:
        """Remove duplicates from array.

        Args:
            arr: Array

        Returns:
            Array with unique values
        """
        if arr is None:
            return []
        seen = set()
        result = []
        for x in arr:
            # Use repr for unhashable types
            key = repr(x) if isinstance(x, (list, dict)) else x
            if key not in seen:
                seen.add(key)
                result.append(x)
        return result

    def get_functions(self) -> Dict[str, Callable]:
        """Get all array functions as dictionary.

        Returns:
            Dictionary of function name to function
        """
        return {
            "create": self.create,
            "from": self.from_value,
            "range": self.range,
            "length": self.length,
            "push": self.push,
            "pop": self.pop,
            "shift": self.shift,
            "unshift": self.unshift,
            "slice": self.slice,
            "concat": self.concat,
            "join": self.join,
            "reverse": self.reverse,
            "sort": self.sort,
            "indexOf": self.index_of,
            "lastIndexOf": self.last_index_of,
            "contains": self.contains,
            "map": self.map,
            "filter": self.filter,
            "reduce": self.reduce,
            "find": self.find,
            "findIndex": self.find_index,
            "every": self.every,
            "some": self.some,
            "flat": self.flat,
            "flatMap": self.flat_map,
            "fill": self.fill,
            "copy": self.copy,
            "unique": self.unique,
        }


__all__ = ["ArrayGlobal"]