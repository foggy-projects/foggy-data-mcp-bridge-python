"""String utilities for Foggy Framework."""

import re
import uuid
from typing import List, Optional, Pattern, Union


class StringUtils:
    """String utility functions."""

    @staticmethod
    def is_empty(s: Optional[str]) -> bool:
        """Check if string is None or empty."""
        return s is None or s == ""

    @staticmethod
    def is_not_empty(s: Optional[str]) -> bool:
        """Check if string is not None and not empty."""
        return s is not None and s != ""

    @staticmethod
    def is_blank(s: Optional[str]) -> bool:
        """Check if string is None, empty, or whitespace only."""
        return s is None or s.strip() == ""

    @staticmethod
    def is_not_blank(s: Optional[str]) -> bool:
        """Check if string is not blank."""
        return s is not None and s.strip() != ""

    @staticmethod
    def default_if_empty(s: Optional[str], default: str) -> str:
        """Return default if string is empty."""
        return s if StringUtils.is_not_empty(s) else default

    @staticmethod
    def default_if_blank(s: Optional[str], default: str) -> str:
        """Return default if string is blank."""
        return s if StringUtils.is_not_blank(s) else default

    @staticmethod
    def trim(s: Optional[str]) -> str:
        """Trim whitespace from string."""
        return s.strip() if s else ""

    @staticmethod
    def truncate(s: str, max_length: int, suffix: str = "...") -> str:
        """Truncate string to max length.

        Args:
            s: String to truncate
            max_length: Maximum length
            suffix: Suffix to append if truncated

        Returns:
            Truncated string
        """
        if len(s) <= max_length:
            return s
        return s[: max_length - len(suffix)] + suffix

    @staticmethod
    def capitalize(s: str) -> str:
        """Capitalize first letter."""
        if not s:
            return s
        return s[0].upper() + s[1:]

    @staticmethod
    def uncapitalize(s: str) -> str:
        """Lowercase first letter."""
        if not s:
            return s
        return s[0].lower() + s[1:]

    @staticmethod
    def camel_to_snake(s: str) -> str:
        """Convert camelCase to snake_case."""
        result = re.sub(r"([A-Z])", r"_\1", s)
        return result.lower().lstrip("_")

    @staticmethod
    def snake_to_camel(s: str, upper_first: bool = False) -> str:
        """Convert snake_case to camelCase.

        Args:
            s: Snake case string
            upper_first: Whether to uppercase first letter (PascalCase)

        Returns:
            CamelCase string
        """
        parts = s.split("_")
        result = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        if upper_first and result:
            result = result[0].upper() + result[1:]
        return result

    @staticmethod
    def camel_to_kebab(s: str) -> str:
        """Convert camelCase to kebab-case."""
        result = re.sub(r"([A-Z])", r"-\1", s)
        return result.lower().lstrip("-")

    @staticmethod
    def kebab_to_camel(s: str, upper_first: bool = False) -> str:
        """Convert kebab-case to camelCase."""
        parts = s.split("-")
        result = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        if upper_first and result:
            result = result[0].upper() + result[1:]
        return result

    @staticmethod
    def split_trim(s: str, delimiter: str = ",") -> List[str]:
        """Split string and trim each part."""
        return [part.strip() for part in s.split(delimiter) if part.strip()]

    @staticmethod
    def join_non_empty(items: List[Optional[str]], delimiter: str = ",") -> str:
        """Join non-empty strings with delimiter."""
        return delimiter.join(item for item in items if StringUtils.is_not_empty(item))

    @staticmethod
    def starts_with_any(s: str, prefixes: List[str]) -> bool:
        """Check if string starts with any of the prefixes."""
        return any(s.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def ends_with_any(s: str, suffixes: List[str]) -> bool:
        """Check if string ends with any of the suffixes."""
        return any(s.endswith(suffix) for suffix in suffixes)

    @staticmethod
    def remove_prefix(s: str, prefix: str) -> str:
        """Remove prefix from string if present."""
        if s.startswith(prefix):
            return s[len(prefix) :]
        return s

    @staticmethod
    def remove_suffix(s: str, suffix: str) -> str:
        """Remove suffix from string if present."""
        if s.endswith(suffix):
            return s[: -len(suffix)]
        return s

    @staticmethod
    def mask(
        s: str, visible_start: int = 2, visible_end: int = 2, mask_char: str = "*"
    ) -> str:
        """Mask string, showing only visible characters.

        Args:
            s: String to mask
            visible_start: Number of visible characters at start
            visible_end: Number of visible characters at end
            mask_char: Character to use for masking

        Returns:
            Masked string
        """
        if len(s) <= visible_start + visible_end:
            return mask_char * len(s)
        return s[:visible_start] + mask_char * (len(s) - visible_start - visible_end) + s[-visible_end:]

    @staticmethod
    def is_numeric(s: str) -> bool:
        """Check if string is numeric."""
        try:
            float(s)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_alpha(s: str) -> bool:
        """Check if string contains only letters."""
        return s.isalpha()

    @staticmethod
    def is_alphanumeric(s: str) -> bool:
        """Check if string contains only letters and numbers."""
        return s.isalnum()

    @staticmethod
    def regex_match(s: str, pattern: Union[str, Pattern]) -> bool:
        """Check if string matches regex pattern."""
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        return bool(pattern.match(s))

    @staticmethod
    def regex_find_all(s: str, pattern: Union[str, Pattern]) -> List[str]:
        """Find all regex matches in string."""
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        return pattern.findall(s)

    @staticmethod
    def regex_replace(s: str, pattern: Union[str, Pattern], replacement: str) -> str:
        """Replace regex matches in string."""
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        return pattern.sub(replacement, s)